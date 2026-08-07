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
from app.config import get_settings
from app.db import SessionLocal
from app.models import VerifyChannel
from app.pipeline.ingest import IngestError, ingest_file, ingest_text
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


def _extract(message: dict) -> tuple[str, str | None, str | None, str | None]:
    """(kind, text, media_id, sim_local_path) for the message shapes we accept.

    sim_local_path is a testing-only key scripts/whatsapp_sim.py adds so a
    real attachment can be exercised without a Meta Business account (see
    channels/whatsapp.download_media) — a real Meta payload never carries it.
    """
    kind = message.get("type", "")
    if kind == "text":
        return "text", (message.get("text") or {}).get("body"), None, None
    if kind in ("image", "video", "document"):
        node = message.get(kind) or {}
        return kind, node.get("caption"), node.get("id"), message.get("_sim_local_path")
    return kind, None, None, None


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
                kind, text, media_id, sim_local_path = _extract(message)
                if not sender:
                    continue
                try:
                    _handle_one(sender, kind, text, media_id, sim_local_path)
                    handled += 1
                except Exception:
                    # 200 regardless — see module docstring on retry storms
                    logger.exception("whatsapp: failed handling message from %s", sender)
    return ok({"handled": handled})


def _handle_one(
    sender: str, kind: str, text: str | None, media_id: str | None, sim_local_path: str | None = None
) -> None:
    """One inbound message → one verdict reply, via the shared pipeline."""
    from app.api.verify import _run_verification  # local import avoids a cycle

    if media_id:
        media = whatsapp.download_media(media_id, sim_local_path)
        if media is None:
            whatsapp.send_text(sender, "Sorry — that attachment could not be downloaded.")
            return
        data, _mime = media
        try:
            ingest_result = ingest_file(data, f"whatsapp.{kind}")
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

    card: dict = {}
    with SessionLocal() as db:
        for kind_, payload in _run_verification(
            db,
            ingest_result,
            claimed_sender_text=text if media_id else None,
            state_code=None,
            channel=VerifyChannel.whatsapp,
            locale=get_settings().default_locale,
        ):
            if kind_ == "result":
                card = payload

    if card:
        from app.channels.render import CardPayload

        whatsapp.send_text(sender, whatsapp.format_card(CardPayload.model_validate(card)))
