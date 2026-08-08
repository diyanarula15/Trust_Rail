"""SMS inbound webhooks. Two real, differently-authenticated routes — see
channels/sms.py's module docstring for why they're genuinely different
integrations, not two ways of writing the same thing.

Both return 200 on internal failure, same reasoning as every other webhook
in this codebase: Twilio (and SMS-forwarder apps generally) retry failed
deliveries aggressively, and a retry storm on one bad message helps nobody.
Problems are logged instead.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select

from app.channels import sms
from app.config import get_settings
from app.db import SessionLocal
from app.models import CircleStatus, TrustCircle
from app.schemas import err, ok

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/sms", tags=["sms"])

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


async def _read_body_text(request: Request) -> tuple[str | None, str | None]:
    """(from_number_or_none, message_body_or_none). Accepts Twilio's real
    inbound-SMS shape (form-encoded From/Body) and, for Auto-Guard's
    generic-forwarder-app case only, a plain JSON body too — those apps
    rarely speak Twilio's exact form contract, and requiring one specific
    vendor's shape would make the guard endpoint unusable for its actual
    purpose. Field names are matched loosely for the same reason."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            return None, None
        frm = body.get("From") or body.get("from") or body.get("sender")
        text = body.get("Body") or body.get("body") or body.get("text") or body.get("message")
        return frm, text
    form = await request.form()
    frm = form.get("From") or form.get("from")
    text = form.get("Body") or form.get("body") or form.get("text") or form.get("message")
    return (str(frm) if frm else None), (str(text) if text else None)


@router.post("")
async def receive_direct(request: Request):
    """A message sent to TrustRail's own Twilio number. Always Twilio, so
    always requires a valid signature — same fail-closed posture as the
    WhatsApp and Telegram webhooks."""
    settings = get_settings()
    if not settings.channel_sms_enabled:
        return ok({"ignored": "channel disabled"})

    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    if not sms.verify_twilio_signature(str(request.url), params, request.headers.get("X-Twilio-Signature")):
        logger.warning("sms webhook: bad or missing Twilio signature")
        return JSONResponse(status_code=403, content=err("bad_signature", "Invalid signature."))

    from_number = params.get("From")
    body = params.get("Body")
    if not from_number or not body:
        return PlainTextResponse(_EMPTY_TWIML, media_type="application/xml")

    try:
        with SessionLocal() as db:
            reply = sms.dispatch_direct(db, from_number, body)
        sms.send_sms(from_number, reply)
    except Exception:
        logger.exception("sms webhook: failed handling direct inbound from %s", from_number)
    return PlainTextResponse(_EMPTY_TWIML, media_type="application/xml")


@router.post("/{guard_token}")
async def receive_guarded(guard_token: str, request: Request):
    """A message that arrived on an Auto-Guard-enrolled phone, forwarded
    here automatically. `guard_token` in the path IS the authentication —
    see TrustCircle.guard_token's field comment for why identity can't come
    from the payload itself. A Twilio signature is verified when present
    (the phone's own number really is a Twilio number) but is not required
    (a generic forwarder app has no way to produce one); either way, an
    unrecognized or inactive token is rejected outright.
    """
    settings = get_settings()
    if not settings.trust_circle_enabled:
        return ok({"ignored": "trust circle disabled"})

    with SessionLocal() as db:
        circle = db.execute(
            select(TrustCircle).where(TrustCircle.guard_token == guard_token)
        ).scalars().first()
        if circle is None or circle.status != CircleStatus.active:
            # Deliberately identical to "processed" from the caller's point of
            # view (still 200) — a forwarder app has no useful way to react to
            # an error, and a distinct response would let someone probe for
            # which guard_tokens exist.
            logger.info("sms guard webhook: unknown or inactive token")
            return ok({"ignored": "unknown or inactive guard token"})

        signature = request.headers.get("X-Twilio-Signature")
        if signature is not None:
            form = await request.form()
            params = {k: str(v) for k, v in form.items()}
            if not sms.verify_twilio_signature(str(request.url), params, signature):
                logger.warning("sms guard webhook: Twilio signature present but invalid")
                return JSONResponse(status_code=403, content=err("bad_signature", "Invalid signature."))
            from_number, body = params.get("From"), params.get("Body")
        else:
            from_number, body = await _read_body_text(request)

        if not body:
            return ok({"ignored": "no message body"})

        # No /circle-command handling here, deliberately: this stream is
        # every message someone ELSE sent TO the elder's phone. A guardian
        # linking their own reply channel does that from wherever they're
        # actually chatting with the bot (WhatsApp/Telegram/email/direct
        # SMS to the bot's own number) — there's no scenario where texting
        # the elder's phone is how you'd do that, so a message that happens
        # to start with "/circle" here is just scanned like anything else.
        try:
            sms.handle_guard_inbound(db, circle, body)
        except Exception:
            logger.exception("sms guard webhook: failed handling inbound for circle %s", circle.id)
        return ok({"handled": 1})
