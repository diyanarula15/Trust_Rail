"""WhatsApp Business adapter (spec §12.2). Flag-gated, off by default.

Deliberately thin. All it does is carry a verdict that `render.py` already
produced into and out of WhatsApp — it never decides anything and never
writes copy. That is the same rule the web UI follows (§12.1), and it is
what keeps one verdict engine serving every channel.

Enable with CHANNEL_WHATSAPP_ENABLED=true plus WHATSAPP_TOKEN,
WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN and WHATSAPP_APP_SECRET.
Without real credentials this module stays inert rather than pretending.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.channels.render import CardPayload
from app.config import get_settings
from app.models import VerifyChannel
from app.pipeline.verify_service import run_verification

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v21.0"

# WhatsApp truncates long bodies; keep well inside the limit.
_MAX_BODY = 3500


def enabled() -> bool:
    s = get_settings()
    return bool(s.channel_whatsapp_enabled and s.whatsapp_token and s.whatsapp_phone_number_id)


def verify_webhook_signature(body: bytes, header: str | None) -> bool:
    """Meta signs every webhook delivery with the app secret.

    Unsigned or wrongly signed payloads are rejected: without this anyone who
    learned the URL could inject fabricated verification traffic, which for a
    system whose entire product is authenticity would be a poor look.
    """
    secret = get_settings().whatsapp_app_secret
    if not secret or not header:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def format_card(card: CardPayload) -> str:
    """A verdict as WhatsApp text.

    Uses the plain-language register — someone reading this on a phone is the
    exact audience it was written for — and every string still comes from the
    API payload, never from here.
    """
    headline = card.plain_headline or card.headline
    body = card.plain_body or card.body
    lines = [f"*{headline}*", "", body]

    reasons = card.plain_reason_strings or card.reason_strings
    if reasons:
        lines += ["", "*Why:*"]
        lines += [f"• {r}" for r in reasons[:4]]

    if card.why and card.why.escalated_by:
        lines += ["", f"*{card.why.escalated_by_label}*"]
        lines += [f"• {r}" for r in card.why.escalated_by[:3]]

    for advice in card.advice[:2]:
        lines += ["", advice]

    for button in card.buttons:
        if button.kind == "certificate" and button.url:
            lines += ["", f"{button.label}: {get_settings().base_url}{button.url}"]

    text = "\n".join(lines)
    return text[:_MAX_BODY]


def build_reply(
    ingest_result: Any, claimed_sender_text: str | None, db: Session,
    sender_external_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Runs the real verification pipeline and formats the real WhatsApp
    reply text. Never sends anything — api/webhooks_whatsapp.py's
    `_handle_one` calls this and then separately calls send_text(); the
    frontend-facing api/sim.py calls this directly and never send_text()
    at all, so it can never trigger a real WhatsApp send regardless of
    what credentials happen to be configured.

    `sender_external_id` is the real sender's WhatsApp number, used only for
    a transient Trust Circle lookup (see app/circle/alerts.py) — api/sim.py
    never passes it, so the /channels demo page can never trigger a real
    guardian alert.

    Returns (text, card) — `card` is the full rendered CardPayload dict,
    included since run_verification() already produced it, for callers
    (api/sim.py) that also want the rich detail view.
    """
    card: dict = {}
    for kind, payload in run_verification(
        db, ingest_result, claimed_sender_text=claimed_sender_text,
        state_code=None, channel=VerifyChannel.whatsapp, locale=get_settings().default_locale,
        sender_external_id=sender_external_id,
    ):
        if kind == "result":
            card = payload
    text = format_card(CardPayload.model_validate(card))
    if card.get("circle_alert_sent"):
        text += "\n\n🚨 Your family member has been notified about this."
    return text, card


def send_text(to: str, text: str) -> bool:
    """Reply to a user. Returns False rather than raising — a failed send
    must never take down the verification that produced it."""
    if not enabled():
        logger.info("whatsapp disabled; reply for %s:\n%s", to, text)
        return False
    s = get_settings()
    try:
        resp = httpx.post(
            f"{GRAPH_BASE}/{s.whatsapp_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {s.whatsapp_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"preview_url": False, "body": text},
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("whatsapp send failed: %s", exc)
        return False


def download_media(media_id: str, sim_local_path: str | None = None) -> tuple[bytes, str] | None:
    """Fetch an inbound attachment. Two hops: metadata, then the binary.

    `sim_local_path` is a testing-only escape hatch (see scripts/whatsapp_sim.py
    and docs/SETUP_WHATSAPP.md): with no Meta Business account, there is no
    real media_id to resolve, so the simulator hands us the bytes to use
    directly instead. A real Meta payload never carries this.
    """
    if sim_local_path:
        with open(sim_local_path, "rb") as f:
            return f.read(), "application/octet-stream"
    if not enabled():
        return None
    s = get_settings()
    headers = {"Authorization": f"Bearer {s.whatsapp_token}"}
    try:
        meta = httpx.get(f"{GRAPH_BASE}/{media_id}", headers=headers, timeout=15.0)
        meta.raise_for_status()
        url = meta.json().get("url")
        if not url:
            return None
        binary = httpx.get(url, headers=headers, timeout=30.0)
        binary.raise_for_status()
        return binary.content, binary.headers.get("content-type", "application/octet-stream")
    except Exception as exc:
        logger.warning("whatsapp media download failed: %s", exc)
        return None
