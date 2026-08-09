"""WhatsApp inbound webhook (spec §12.2). Flag-gated, off by default.

A forwarded message arrives here, goes through exactly the same
`_run_verification` pipeline the web UI uses, and the verdict goes back as a
WhatsApp reply. No separate logic, no separate verdict engine — the channel
is a transport, which is the only way the answers can be guaranteed
identical across channels.

Returns 200 to Meta even on internal failure: Meta retries non-200 responses
aggressively, and a retry storm on a failing message helps nobody. Problems
are logged instead.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.channels import whatsapp
from app.circle import pairing as circle_pairing
from app.config import get_settings
from app.db import SessionLocal, get_redis
from app.models import CircleChannel
from app.pipeline.ingest import IngestError, ingest_file, ingest_text
from app.pipeline.verify_service import rate_limit
from app.schemas import err, ok

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/whatsapp", tags=["whatsapp"])


@router.get("")
def verify_subscription(request: Request):
    """Meta's subscription handshake: echo hub.challenge if the token matches."""
    settings = get_settings()
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token")
        and params.get("hub.verify_token") == settings.whatsapp_verify_token
    ):
        return PlainTextResponse(params.get("hub.challenge", ""))
    return JSONResponse(status_code=403, content=err("forbidden", "Verification token mismatch."))


def _extract(message: dict) -> tuple[str, str | None, str | None, str | None, str | None]:
    """(kind, text, media_id, sim_local_path, filename) for the message shapes
    we accept.

    sim_local_path is a testing-only key scripts/whatsapp_sim.py adds so a
    real attachment can be exercised without a Meta Business account (see
    channels/whatsapp.download_media) — a real Meta payload never carries it.

    filename is Meta's real field on document messages (images/videos don't
    carry one) — passed through so ingest_file() gets the sender's actual
    filename instead of a synthetic "whatsapp.document", which matters for
    e.g. a forwarded .eml relying on its extension to sniff correctly.
    """
    kind = message.get("type", "")
    if kind == "text":
        return "text", (message.get("text") or {}).get("body"), None, None, None
    if kind in ("image", "video", "document"):
        node = message.get(kind) or {}
        return kind, node.get("caption"), node.get("id"), message.get("_sim_local_path"), node.get("filename")
    return kind, None, None, None, None


@router.post("")
async def receive(request: Request):
    settings = get_settings()
    raw = await request.body()

    if not settings.channel_whatsapp_enabled:
        return ok({"ignored": "channel disabled"})

    if not whatsapp.verify_webhook_signature(raw, request.headers.get("X-Hub-Signature-256")):
        logger.warning("whatsapp webhook: bad or missing signature")
        return JSONResponse(status_code=403, content=err("bad_signature", "Invalid signature."))

    try:
        payload = await request.json()
    except Exception:
        return ok({"ignored": "unparseable payload"})

    handled = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for message in (change.get("value") or {}).get("messages", []):
                sender = message.get("from")
                kind, text, media_id, sim_local_path, filename = _extract(message)
                if not sender:
                    continue
                try:
                    _handle_one(sender, kind, text, media_id, sim_local_path, filename)
                    handled += 1
                except Exception:
                    # 200 regardless — see module docstring on retry storms
                    logger.exception("whatsapp: failed handling message from %s", sender)
    return ok({"handled": handled})


def _handle_one(
    sender: str, kind: str, text: str | None, media_id: str | None,
    sim_local_path: str | None = None, filename: str | None = None,
) -> None:
    """One inbound message → one verdict reply, via the shared pipeline."""
    settings = get_settings()
    allowed, retry_after = rate_limit(get_redis(), f"whatsapp:{sender}", settings.verify_rate_limit_per_min)
    if not allowed:
        whatsapp.send_text(sender, f"Too many requests. Try again in {retry_after}s.")
        return

    if kind == "text" and text and text.strip():
        with SessionLocal() as db:
            circle_reply = circle_pairing.handle_circle_command(db, CircleChannel.whatsapp, sender, text)
        if circle_reply is not None:
            whatsapp.send_text(sender, circle_reply)
            return

    if media_id:
        media = whatsapp.download_media(media_id, sim_local_path)
        if media is None:
            whatsapp.send_text(sender, "Sorry, that attachment could not be downloaded.")
            return
        data, _mime = media
        try:
            ingest_result = ingest_file(data, filename or f"whatsapp.{kind}")
        except IngestError as exc:
            whatsapp.send_text(sender, exc.message)
            return
    elif text and text.strip():
        try:
            ingest_result = ingest_text(text)
        except IngestError as exc:
            whatsapp.send_text(sender, exc.message)
            return
    else:
        whatsapp.send_text(
            sender,
            "Forward a message, screenshot, PDF or video and I'll check whether a registered "
            "company really published it.",
        )
        return

    with SessionLocal() as db:
        text_reply, _card = whatsapp.build_reply(
            ingest_result, text if media_id else None, db, sender_external_id=sender
        )
    whatsapp.send_text(sender, text_reply)
