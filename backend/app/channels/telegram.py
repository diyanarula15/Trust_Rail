"""Telegram Bot API adapter. Plain HTTPS calls (httpx) — no SDK needed, the
Bot API is just a REST interface. Long-polling (getUpdates) needs no public
URL, unlike WhatsApp's webhook, so this is the one channel that can go fully
live without any tunnel/deployment.

is_live() gates real-vs-simulated the same way channels/whatsapp.py does:
with no token configured, dispatch_update() still runs the real verification
pipeline end-to-end, it just logs the outgoing message instead of calling
sendMessage.
"""
import hmac
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.channels.util import card_buttons
from app.circle import pairing as circle_pairing
from app.config import get_settings
from app.db import get_redis
from app.models import CircleChannel, VerifyChannel
from app.pipeline.ingest import ingest_file, ingest_text
from app.pipeline.verify_service import rate_limit, run_verification

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org"
_FILE_BASE = "https://api.telegram.org/file"
_TELEGRAM_FILE_LIMIT_BYTES = 20 * 1024 * 1024  # Bot API hard cap, independent of settings.max_video_bytes


def is_live() -> bool:
    return bool(get_settings().telegram_bot_token)


def _client() -> httpx.Client:
    return httpx.Client(timeout=40.0)  # getUpdates long-polls up to 30s server-side


def get_updates(offset: int | None, timeout: int = 30) -> list[dict[str, Any]]:
    token = get_settings().telegram_bot_token
    params: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset is not None:
        params["offset"] = offset
    with _client() as client:
        resp = client.get(f"{_API_BASE}/bot{token}/getUpdates", params=params)
        resp.raise_for_status()
        return resp.json()["result"]


def delete_webhook() -> None:
    """getUpdates 409s if a webhook was ever registered for this token —
    idempotent and harmless to call even if none was set."""
    token = get_settings().telegram_bot_token
    with _client() as client:
        client.get(f"{_API_BASE}/bot{token}/deleteWebhook")


def set_webhook(url: str, secret_token: str | None = None) -> dict[str, Any]:
    """Registers a real webhook with Telegram (mirrors WhatsApp's push model
    instead of getUpdates polling). Mutually exclusive with polling — this
    is why scripts/telegram_poll.py calls delete_webhook() at startup, and
    why going live with a webhook means scripts/telegram_poll.py must not
    also be running against the same token."""
    token = get_settings().telegram_bot_token
    payload: dict[str, Any] = {"url": url, "allowed_updates": ["message"]}
    if secret_token:
        payload["secret_token"] = secret_token
    with _client() as client:
        resp = client.post(f"{_API_BASE}/bot{token}/setWebhook", json=payload)
        resp.raise_for_status()
        return resp.json()


def verify_webhook_secret(header: str | None) -> bool:
    """Telegram's equivalent of WhatsApp's X-Hub-Signature-256: a shared
    secret you chose when calling set_webhook(), echoed back by Telegram on
    every delivery as X-Telegram-Bot-Api-Secret-Token. Fails closed, same
    posture as channels/whatsapp.verify_webhook_signature — with no secret
    configured, every request is rejected rather than trusted by default."""
    secret = get_settings().telegram_webhook_secret
    if not secret or not header:
        return False
    return hmac.compare_digest(secret, header)


def get_file_path(file_id: str) -> str:
    token = get_settings().telegram_bot_token
    with _client() as client:
        resp = client.get(f"{_API_BASE}/bot{token}/getFile", params={"file_id": file_id})
        resp.raise_for_status()
        return resp.json()["result"]["file_path"]


def download_file(file_path: str) -> bytes:
    token = get_settings().telegram_bot_token
    with _client() as client:
        resp = client.get(f"{_FILE_BASE}/bot{token}/{file_path}")
        resp.raise_for_status()
        return resp.content


def send_message(chat_id: int | str, text: str, buttons: list[dict[str, str]]) -> dict[str, Any]:
    """Real send when live; logs and returns the composed payload otherwise."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if buttons:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": b["label"], "url": b["url"]}] for b in buttons]
        }
    if not is_live():
        logger.info("telegram sim send to %s: %s", chat_id, payload)
        return payload
    token = get_settings().telegram_bot_token
    with _client() as client:
        resp = client.post(f"{_API_BASE}/bot{token}/sendMessage", json=payload)
        resp.raise_for_status()
        return resp.json()


def _format_reply(card: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    lines = [f"<b>{card['plain_headline']}</b>", "", card["plain_body"]]
    if card.get("plain_reason_strings"):
        lines.append("")
        lines.extend(f"• {r}" for r in card["plain_reason_strings"])
    if card.get("advice"):
        lines.append("")
        lines.extend(card["advice"])
    return "\n".join(lines), card_buttons(card)


def _ingest_from_message(message: dict[str, Any]) -> tuple[Any, str | None]:
    """Returns (IngestResult, claimed_sender_text). Downloads real media via
    the Bot API when live; in sim mode reads bytes from the sim-only
    "_sim_local_path" key a real Telegram payload never carries."""
    caption = message.get("caption")
    sim_path = message.get("_sim_local_path")

    if "text" in message:
        return ingest_text(message["text"]), caption

    if "photo" in message:
        filename = "photo.jpg"
        if sim_path:
            data = open(sim_path, "rb").read()
        else:
            largest = message["photo"][-1]
            data = download_file(get_file_path(largest["file_id"]))
        return ingest_file(data, filename), caption

    if "document" in message:
        filename = message["document"].get("file_name") or "document"
        if sim_path:
            data = open(sim_path, "rb").read()
        else:
            if message["document"].get("file_size", 0) > _TELEGRAM_FILE_LIMIT_BYTES:
                raise ValueError("file too large for this bot to fetch (20MB Telegram Bot API limit)")
            data = download_file(get_file_path(message["document"]["file_id"]))
        return ingest_file(data, filename), caption

    if "video" in message:
        filename = "video.mp4"
        if sim_path:
            data = open(sim_path, "rb").read()
        else:
            if message["video"].get("file_size", 0) > _TELEGRAM_FILE_LIMIT_BYTES:
                raise ValueError("file too large for this bot to fetch (20MB Telegram Bot API limit)")
            data = download_file(get_file_path(message["video"]["file_id"]))
        return ingest_file(data, filename), caption

    raise ValueError("unsupported Telegram message type (expected text/photo/document/video)")


def build_reply(
    ingest_result: Any, claimed_sender_text: str | None, db: Session,
    sender_external_id: str | None = None,
) -> tuple[str, list[dict[str, str]], dict[str, Any]]:
    """Runs the real verification pipeline and formats the real Telegram
    reply text + buttons. Never sends anything — dispatch_update() calls
    this and then separately calls send_message(); the frontend-facing
    api/sim.py calls this directly and never send_message() at all, so it
    can never trigger a real Telegram send regardless of what credentials
    happen to be configured.

    `sender_external_id` is the real sender's chat_id, used only for a
    transient Trust Circle lookup (see app/circle/alerts.py) — api/sim.py
    never passes it, so the /channels demo page can never trigger a real
    guardian alert.

    Returns (text, buttons, card) — `card` is the full rendered CardPayload
    dict, included since run_verification() already produced it, for
    callers (api/sim.py) that also want the rich detail view.
    """
    card: dict = {}
    for kind, payload in run_verification(
        db, ingest_result, claimed_sender_text=claimed_sender_text,
        state_code=None, channel=VerifyChannel.telegram, locale="en",
        sender_external_id=sender_external_id,
    ):
        if kind == "result":
            card = payload

    text, buttons = _format_reply(card)
    if card.get("circle_alert_sent"):
        text += "\n\n🚨 Your family member has been notified about this."
    return text, buttons, card


def dispatch_update(update: dict[str, Any], db: Session) -> dict[str, Any] | None:
    """Handles one Telegram update end-to-end: ingest -> build_reply() ->
    real-or-logged send. Returns the sent (or sim-logged) payload, or None
    if the update carried no message to act on.

    Shared by the real long-poll loop (scripts/telegram_poll.py), the
    webhook (api/webhooks_telegram.py) and the local simulator
    (scripts/telegram_sim.py) — all call this exact function, so the sim
    path exercises real handling logic, not a mock.
    """
    message = update.get("message")
    if message is None:
        return None
    chat_id = message["chat"]["id"]
    settings = get_settings()

    allowed, retry_after = rate_limit(get_redis(), f"telegram:{chat_id}", settings.verify_rate_limit_per_min)
    if not allowed:
        return send_message(chat_id, f"Too many requests. Try again in {retry_after}s.", [])

    incoming_text = message.get("text")
    if incoming_text:
        circle_reply = circle_pairing.handle_circle_command(
            db, CircleChannel.telegram, str(chat_id), incoming_text
        )
        if circle_reply is not None:
            return send_message(chat_id, circle_reply, [])

    try:
        ingest_result, claimed_sender_text = _ingest_from_message(message)
    except Exception as exc:
        return send_message(chat_id, f"Couldn't process that message: {exc}", [])

    text, buttons, _card = build_reply(
        ingest_result, claimed_sender_text, db, sender_external_id=str(chat_id)
    )
    return send_message(chat_id, text, buttons)
