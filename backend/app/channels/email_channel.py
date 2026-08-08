"""Email adapter: IMAP polling + SMTP reply. Stdlib only (imaplib/smtplib/
email) — no new dependencies. Polling needs no public URL, same as Telegram.

is_live() gates real-vs-simulated the same way as the other two channels:
with no mailbox configured, handle_raw_message() still runs the real
verification pipeline end-to-end, it just logs the composed reply instead of
sending it over SMTP.
"""
import email as email_stdlib
import imaplib
import logging
import smtplib
from email.message import EmailMessage
from email.policy import default as email_policy
from email.utils import parseaddr
from typing import Any, NamedTuple

from sqlalchemy.orm import Session

from app.channels.util import card_buttons
from app.circle import pairing as circle_pairing
from app.config import get_settings
from app.db import get_redis
from app.models import CircleChannel, VerifyChannel
from app.pipeline.emailcheck import parse_eml
from app.pipeline.ingest import ingest_eml_bytes
from app.pipeline.verify_service import rate_limit, run_verification

logger = logging.getLogger(__name__)


class _TransportHeaders(NamedTuple):
    """Headers parse_eml() doesn't capture because they're irrelevant to
    verification but are needed for reply-threading and loop-prevention —
    parsed separately here rather than extending the gate-tested
    emailcheck.py for unrelated concerns."""
    message_id: str | None
    references: str | None
    auto_submitted: str
    content_type: str


def _transport_headers(raw: bytes) -> _TransportHeaders:
    msg = email_stdlib.message_from_bytes(raw, policy=email_policy)
    return _TransportHeaders(
        message_id=msg.get("Message-ID"),
        references=msg.get("References"),
        auto_submitted=str(msg.get("Auto-Submitted", "no")).lower(),
        content_type=str(msg.get("Content-Type", "")).lower(),
    )


def is_live() -> bool:
    settings = get_settings()
    return bool(settings.email_imap_host and settings.email_username)


def _is_auto_generated(from_addr: str, headers: _TransportHeaders) -> bool:
    """Loop-prevention: never reply to our own mail, out-of-office/auto-
    responders (RFC 3834), or bounces/DSNs — the single biggest way a demo
    email bot ends up in an infinite reply loop with a real inbox."""
    settings = get_settings()
    addr = parseaddr(from_addr)[1].lower()
    if settings.email_username and addr == settings.email_username.lower():
        return True
    if headers.auto_submitted not in ("", "no"):
        return True
    if addr.startswith(("mailer-daemon@", "postmaster@")):
        return True
    if "multipart/report" in headers.content_type:
        return True
    return False


def _format_reply_text(card: dict[str, Any]) -> str:
    lines = [card["plain_headline"], "", card["plain_body"]]
    if card.get("plain_reason_strings"):
        lines.append("")
        lines.extend(f"- {r}" for r in card["plain_reason_strings"])
    if card.get("advice"):
        lines.append("")
        lines.extend(card["advice"])
    for b in card_buttons(card):
        lines.append(f"\n{b['label']}: {b['url']}")
    return "\n".join(lines)


def _send_reply(*, to_addr: str, subject: str, body: str, in_reply_to: str | None,
                 references: str | None) -> EmailMessage:
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = settings.email_username
    msg["To"] = to_addr
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    msg["Auto-Submitted"] = "auto-replied"
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = f"{references} {in_reply_to}".strip() if references else in_reply_to
    msg.set_content(body)

    if not is_live():
        logger.info("email sim send to %s: %s", to_addr, body)
        return msg

    with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port) as smtp:
        smtp.starttls()
        smtp.login(settings.email_username, settings.email_password)
        smtp.send_message(msg)
    return msg


def handle_raw_message(raw: bytes, db: Session) -> EmailMessage | None:
    """Handles one raw .eml message end-to-end: parse -> loop-prevention
    checks -> real verification pipeline -> composed reply -> real-or-logged
    SMTP send. Returns the composed EmailMessage, or None if this message was
    skipped (self-sent / auto-responder / bounce — no reply is ever sent for
    these).

    Called by both the real IMAP poller (scripts/email_poll.py) and the
    local simulator (scripts/email_sim.py) — both call this exact function,
    so the sim path exercises real handling logic, not a mock.
    """
    parsed = parse_eml(raw)
    headers = _transport_headers(raw)
    if _is_auto_generated(parsed.from_addr or "", headers):
        logger.info("skipping auto-generated/self-sent message from %s", parsed.from_addr)
        return None

    from_addr = parseaddr(parsed.reply_to or parsed.from_addr or "")[1]
    settings = get_settings()

    allowed, retry_after = rate_limit(get_redis(), f"email:{from_addr}", settings.verify_rate_limit_per_min)
    if not allowed:
        return _send_reply(
            to_addr=from_addr, subject=parsed.subject,
            body=f"Too many requests. Try again in {retry_after}s.",
            in_reply_to=headers.message_id, references=headers.references,
        )

    circle_reply = circle_pairing.handle_circle_command(
        db, CircleChannel.email, from_addr, f"{parsed.subject or ''}\n{parsed.body_text or ''}"
    )
    if circle_reply is not None:
        return _send_reply(
            to_addr=from_addr, subject=parsed.subject, body=circle_reply,
            in_reply_to=headers.message_id, references=headers.references,
        )

    ingest_result = ingest_eml_bytes(raw)
    card: dict = {}
    for kind, payload in run_verification(
        db, ingest_result, claimed_sender_text=None,
        state_code=None, channel=VerifyChannel.email, locale="en",
        sender_external_id=from_addr,
    ):
        if kind == "result":
            card = payload

    body = _format_reply_text(card)
    if card.get("circle_alert_sent"):
        body += "\n\n🚨 Your family member has been notified about this."

    return _send_reply(
        to_addr=from_addr, subject=parsed.subject, body=body,
        in_reply_to=headers.message_id, references=headers.references,
    )


def fetch_unseen(imap: imaplib.IMAP4_SSL) -> list[tuple[int, bytes]]:
    """(uid, raw_bytes) for every UNSEEN message. Fetches with BODY.PEEK[]
    rather than RFC822 — the latter side-effects marking the message \\Seen
    on fetch, so a crash between fetch and successful handling would lose
    the message silently (it'd never show as UNSEEN again)."""
    status, data = imap.search(None, "UNSEEN")
    if status != "OK":
        return []
    out = []
    for num in data[0].split():
        status, msg_data = imap.fetch(num, "(BODY.PEEK[])")
        if status == "OK" and msg_data and msg_data[0]:
            out.append((int(num), msg_data[0][1]))
    return out


def mark_seen(imap: imaplib.IMAP4_SSL, uid: int) -> None:
    imap.store(str(uid), "+FLAGS", "\\Seen")


def connect_imap() -> imaplib.IMAP4_SSL:
    settings = get_settings()
    imap = imaplib.IMAP4_SSL(settings.email_imap_host, settings.email_imap_port)
    imap.login(settings.email_username, settings.email_password)
    imap.select("INBOX")
    return imap
