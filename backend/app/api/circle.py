"""Trust Circle API: web-dashboard pairing completion + management.

No auth system exists in TrustRail — possession of `circle_token` (an
unguessable random token, the same bearer-capability pattern already used
for certificate links via `models.ViewToken`) is what proves you're the
guardian for a given circle.
"""
import secrets

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.circle import pairing
from app.config import get_settings
from app.db import get_db
from app.models import CircleAlert, CircleStatus, TrustCircle
from app.schemas import err, ok

router = APIRouter(prefix="/api/circle", tags=["circle"])


def _bad(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content=err(code, message))


class PairComplete(BaseModel):
    code: str
    guardian_name: str
    guardian_email: str


def _mask(channel: str, external_id: str) -> str:
    if channel == "email":
        local, _, domain = external_id.partition("@")
        return f"{local[:1]}***@{domain}" if domain else "***"
    return f"***{external_id[-4:]}" if len(external_id) > 4 else "***"


def _guard_webhook_url(guard_token: str) -> str:
    return f"{get_settings().api_base_url.rstrip('/')}/api/webhooks/sms/{guard_token}"


def _status_out(circle: TrustCircle, db: Session) -> dict:
    alerts = db.execute(
        select(CircleAlert)
        .where(CircleAlert.circle_id == circle.id)
        .order_by(CircleAlert.created_at.desc())
        .limit(20)
    ).scalars().all()
    return {
        "status": circle.status.value,
        "elder_channel": circle.elder_channel.value,
        "elder_masked": _mask(circle.elder_channel.value, circle.elder_external_id),
        "guardian_name": circle.guardian_name,
        "guardian_email": circle.guardian_email,
        "guardian_channel": circle.guardian_channel.value if circle.guardian_channel else None,
        "guard_enabled": circle.guard_token is not None,
        "guard_webhook_url": _guard_webhook_url(circle.guard_token) if circle.guard_token else None,
        "alerts": [
            {
                "verdict": a.verdict,
                "plain_headline": a.plain_headline,
                "campaign": a.campaign,
                "delivered_via": a.delivered_via,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ],
    }


@router.post("/pair/complete")
def pair_complete(body: PairComplete, db: Session = Depends(get_db)):
    if not body.guardian_name.strip() or not body.guardian_email.strip():
        return _bad(422, "bad_input", "Guardian name and email are required.")
    circle = pairing.complete_web_pairing(db, body.code.strip(), body.guardian_name, body.guardian_email)
    if circle is None:
        return _bad(400, "invalid_or_expired", "That code isn't valid or has expired.")
    return ok({"circle_token": circle.circle_token})


@router.get("/{circle_token}")
def get_status(circle_token: str, db: Session = Depends(get_db)):
    circle = pairing.get_by_token(db, circle_token)
    if circle is None:
        return _bad(404, "not_found", "No such Trust Circle.")
    return ok(_status_out(circle, db))


@router.post("/{circle_token}/revoke")
def revoke_circle(circle_token: str, db: Session = Depends(get_db)):
    if not pairing.revoke(db, circle_token):
        return _bad(404, "not_found", "No such Trust Circle.")
    return ok({"status": "revoked"})


def _require_active(db: Session, circle_token: str) -> TrustCircle | JSONResponse:
    circle = pairing.get_by_token(db, circle_token)
    if circle is None:
        return _bad(404, "not_found", "No such Trust Circle.")
    if circle.status != CircleStatus.active:
        return _bad(409, "not_active", "This Trust Circle isn't active yet.")
    return circle


@router.post("/{circle_token}/guard")
def enable_guard(circle_token: str, db: Session = Depends(get_db)):
    """Turns on Auto-Guard: mints (or returns the existing) unguessable
    webhook token that an SMS-forwarder app or Twilio number gets pointed
    at. Idempotent on purpose — re-clicking "enable" in the UI must not
    invalidate an already-configured forwarder."""
    circle = _require_active(db, circle_token)
    if isinstance(circle, JSONResponse):
        return circle
    if circle.guard_token is None:
        circle.guard_token = secrets.token_urlsafe(24)
        db.commit()
    return ok({"guard_token": circle.guard_token, "webhook_url": _guard_webhook_url(circle.guard_token)})


@router.post("/{circle_token}/guard/regenerate")
def regenerate_guard(circle_token: str, db: Session = Depends(get_db)):
    """Issues a fresh token, invalidating whatever forwarder app or Twilio
    number was previously configured with the old one — for when a device
    was lost, or the setup needs to move to a different phone."""
    circle = _require_active(db, circle_token)
    if isinstance(circle, JSONResponse):
        return circle
    circle.guard_token = secrets.token_urlsafe(24)
    db.commit()
    return ok({"guard_token": circle.guard_token, "webhook_url": _guard_webhook_url(circle.guard_token)})


@router.post("/{circle_token}/guard/disable")
def disable_guard(circle_token: str, db: Session = Depends(get_db)):
    circle = pairing.get_by_token(db, circle_token)
    if circle is None:
        return _bad(404, "not_found", "No such Trust Circle.")
    circle.guard_token = None
    db.commit()
    return ok({"guard_enabled": False})
