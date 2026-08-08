"""Telegram inbound webhook. Push-based alternative to
scripts/telegram_poll.py's getUpdates loop — mutually exclusive with
polling at the Telegram API level (a token can have at most one active
webhook OR be polled via getUpdates, never both; see
channels.telegram.set_webhook / delete_webhook).

A forwarded message arrives here and goes through exactly the same
dispatch_update() the poller and the in-process simulator
(scripts/telegram_sim.py) use — one shared handler, so the verdict can
never drift by transport, mirroring api/webhooks_whatsapp.py's design.

Returns 200 even on internal failure, same reasoning as the WhatsApp
webhook: Telegram retries non-200 deliveries aggressively, and a retry
storm on a failing update helps nobody. Problems are logged instead.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.channels import telegram
from app.config import get_settings
from app.db import SessionLocal
from app.schemas import err, ok

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/telegram", tags=["telegram"])


@router.post("")
async def receive(request: Request):
    settings = get_settings()

    if not settings.channel_telegram_enabled:
        return ok({"ignored": "channel disabled"})

    if not telegram.verify_webhook_secret(request.headers.get("X-Telegram-Bot-Api-Secret-Token")):
        logger.warning("telegram webhook: bad or missing secret token")
        return JSONResponse(status_code=403, content=err("bad_secret", "Invalid secret token."))

    try:
        update = await request.json()
    except Exception:
        return ok({"ignored": "unparseable payload"})

    try:
        with SessionLocal() as db:
            telegram.dispatch_update(update, db)
        return ok({"handled": 1})
    except Exception:
        # 200 regardless — see module docstring on retry storms
        logger.exception("telegram webhook: failed handling update %s", update.get("update_id"))
        return ok({"handled": 0})
