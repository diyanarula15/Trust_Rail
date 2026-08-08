"""SMS adapter. Plain HTTPS to Twilio's REST API (httpx) — no SDK, same
convention as channels/telegram.py.

Two genuinely different real-world integration shapes share this file:

1. **Direct** — a dedicated Twilio number people text the bot at, same
   two-way pattern as WhatsApp/Telegram/email: text arrives, a verdict
   reply texts back. `dispatch_direct()` / `POST /api/webhooks/sms`.

2. **Auto-Guard** — the actual point of this feature. A phone's own
   SMS-forwarder app (real, downloadable apps like "SMS Forwarder" or "SMS
   Gateway" already do exactly this — see docs/SETUP_SMS.md) mirrors every
   inbound text to a URL the instant it arrives, before anyone opens their
   messaging app. There is no reply-to-sender here (replying to a scammer's
   number helps nobody, and the elder never chose to "ask the bot" — the
   scan is invisible to them by design); the only outward effect is a
   guardian alert if the message turns out to be dangerous.
   `handle_guard_inbound()` / `POST /api/webhooks/sms/{guard_token}`.

is_live() gates real-vs-simulated the same way every other channel does:
with no Twilio credentials configured, both paths still run the real
verification pipeline end-to-end, they just log the reply instead of
sending it.
"""
import base64
import hashlib
import hmac
import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.channels.util import card_buttons
from app.circle import pairing as circle_pairing
from app.config import get_settings
from app.db import get_redis
from app.models import CircleChannel, TrustCircle, VerifyChannel
from app.pipeline.ingest import ingest_text
from app.pipeline.verify_service import rate_limit, run_verification

logger = logging.getLogger(__name__)

_API_BASE = "https://api.twilio.com/2010-04-01"


def is_live() -> bool:
    s = get_settings()
    return bool(s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_number)


def verify_twilio_signature(url: str, params: dict[str, str], header: str | None) -> bool:
    """Twilio's actual signing scheme (documented at twilio.com/docs/usage/
    webhooks/webhooks-security): sort the POSTed params by key, append each
    key+value directly onto the full request URL with no separator, HMAC-SHA1
    with the auth token, base64-encode, compare to X-Twilio-Signature.

    Fails closed with no auth token configured — same posture as every other
    channel's signature check in this codebase (WhatsApp's HMAC-SHA256,
    Telegram's shared-secret header): reject rather than trust by default.
    """
    token = get_settings().twilio_auth_token
    if not token or not header:
        return False
    data = url + "".join(f"{k}{v}" for k, v in sorted(params.items()))
    expected = base64.b64encode(
        hmac.new(token.encode(), data.encode("utf-8"), hashlib.sha1).digest()
    ).decode()
    return hmac.compare_digest(expected, header)


def _client() -> httpx.Client:
    return httpx.Client(timeout=20.0)


def send_sms(to: str, body: str) -> dict[str, Any]:
    """Real send when live; logs and returns the composed payload otherwise."""
    settings = get_settings()
    payload = {"To": to, "From": settings.twilio_from_number, "Body": body}
    if not is_live():
        logger.info("sms sim send to %s: %s", to, body)
        return payload
    with _client() as client:
        resp = client.post(
            f"{_API_BASE}/Accounts/{settings.twilio_account_sid}/Messages.json",
            data=payload,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        )
        resp.raise_for_status()
        return resp.json()


def _format_reply(card: dict[str, Any]) -> str:
    """SMS has no formatting and traditionally little room, so this is the
    tightest of any channel's reply — headline, one reason, one link."""
    lines = [card["plain_headline"], card["plain_body"]]
    reasons = card.get("plain_reason_strings") or []
    if reasons:
        lines.append(reasons[0])
    buttons = card_buttons(card)
    if buttons:
        lines.append(buttons[0]["url"])
    return "\n".join(lines)


def build_reply(db: Session, body: str, sender_external_id: str | None = None) -> str:
    """Runs the real verification pipeline and formats the real SMS reply.
    Never sends anything itself.

    Deliberately does NOT handle /circle pairing commands, and takes no
    rate-limit action of its own — see dispatch_direct() below for why, and
    mirror telegram.build_reply's identical split for the same reason:
    api/sim.py's demo page calls this directly and must never be able to
    complete a real pairing or trigger a real guardian alert, regardless of
    what a user types into it. With sender_external_id left at its default
    (None), maybe_alert_guardians() (called inside run_verification) can't
    look anyone up, so a demo-page click is structurally incapable of
    alerting a real guardian — not just unlikely to.
    """
    card: dict = {}
    for kind, payload in run_verification(
        db, ingest_text(body), claimed_sender_text=None, state_code=None,
        channel=VerifyChannel.sms, locale="en", sender_external_id=sender_external_id,
    ):
        if kind == "result":
            card = payload
    text = _format_reply(card)
    if card.get("circle_alert_sent"):
        text += "\nYour family has been notified."
    return text


def dispatch_direct(db: Session, from_number: str, body: str) -> str:
    """The real entrypoint for a message sent to TrustRail's own Twilio
    number: rate limit, /circle pairing commands, then build_reply() with
    the real sender identity attached. Only ever called from the signed
    webhook (api/webhooks_sms.py) — never from api/sim.py, which is exactly
    what keeps the demo page safe (see build_reply's docstring)."""
    settings = get_settings()
    allowed, retry_after = rate_limit(get_redis(), f"sms:{from_number}", settings.verify_rate_limit_per_min)
    if not allowed:
        return f"Too many requests. Try again in {retry_after}s."

    circle_reply = circle_pairing.handle_circle_command(db, CircleChannel.sms, from_number, body)
    if circle_reply is not None:
        return circle_reply

    return build_reply(db, body, sender_external_id=from_number)


def handle_guard_inbound(db: Session, circle: TrustCircle, body: str) -> dict:
    """Auto-Guard path: `body` is a message that arrived on `circle`'s own
    phone, forwarded here automatically. Runs the identical pipeline as
    every other channel — same hashing, same registry match, same strict
    escalation policy — the only difference from `dispatch_direct` is
    what happens with the result: nothing is sent back to whoever sent the
    original message, and the alert (if any) targets this specific circle
    directly via `also_alert_circle_id` rather than an identity lookup,
    since there is no elder identity anywhere in this payload to look up
    (see the `guard_token` field comment on TrustCircle).

    Returns the rendered card for logging/testing — never delivered anywhere.
    """
    card: dict = {}
    for kind, payload in run_verification(
        db, ingest_text(body), claimed_sender_text=None, state_code=None,
        channel=VerifyChannel.sms, locale="en", sender_external_id=None,
        also_alert_circle_id=circle.id,
    ):
        if kind == "result":
            card = payload
    return card
