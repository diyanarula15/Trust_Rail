"""Trust Circle API: web-dashboard pairing completion + management.

No auth system exists in TrustRail — possession of `circle_token` (an
unguessable random token, the same bearer-capability pattern already used
for certificate links via `models.ViewToken`) is what proves you're the
guardian for a given circle.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.circle import pairing
from app.db import get_db
from app.models import CircleAlert, TrustCircle
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
