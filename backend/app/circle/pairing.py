"""Trust Circle pairing: linking an elder's channel identity to a guardian
who gets alerted when the verification pipeline flags something they sent.

No auth system exists in TrustRail (its whole product is anonymous,
stateless verification) — so circle management reuses the same
bearer-capability-token pattern already used for certificate links
(models.ViewToken): possession of `circle_token` is what proves you're the
guardian for a given circle, nothing else.
"""
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.channels.render import _Defaulting, _load
from app.config import get_settings
from app.models import CircleChannel, CircleStatus, TrustCircle

# Matched per-line, not as a substring search, so this can never accidentally
# fire on forwarded scam content that happens to mention "circle".
_COMMAND_RE = re.compile(r"^/circle(?:\s+(\d{6}))?$", re.IGNORECASE)


def _generate_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def _generate_token() -> str:
    return secrets.token_urlsafe(24)


def normalize_external_id(channel: CircleChannel, external_id: str) -> str:
    external_id = external_id.strip()
    return external_id.lower() if channel == CircleChannel.email else external_id


def _find_for_elder(db: Session, channel: CircleChannel, external_id: str) -> TrustCircle | None:
    return db.execute(
        select(TrustCircle)
        .where(
            TrustCircle.elder_channel == channel,
            TrustCircle.elder_external_id == external_id,
            TrustCircle.status != CircleStatus.revoked,
        )
        .order_by(TrustCircle.created_at.desc())
    ).scalars().first()


def start_pairing(db: Session, channel: CircleChannel, external_id: str) -> TrustCircle:
    """Elder-side: bare `/circle`. Reuses an existing pending/active circle
    for this identity rather than creating duplicates, just refreshing the
    code and its expiry."""
    settings = get_settings()
    external_id = normalize_external_id(channel, external_id)
    circle = _find_for_elder(db, channel, external_id)
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.circle_pairing_code_ttl_minutes)
    if circle is None:
        circle = TrustCircle(
            elder_channel=channel,
            elder_external_id=external_id,
            pairing_code=_generate_code(),
            pairing_code_expires_at=expires_at,
            status=CircleStatus.pending,
        )
        db.add(circle)
    else:
        circle.pairing_code = _generate_code()
        circle.pairing_code_expires_at = expires_at
    db.commit()
    return circle


def _find_by_code(db: Session, code: str) -> TrustCircle | None:
    circle = db.execute(
        select(TrustCircle)
        .where(TrustCircle.pairing_code == code, TrustCircle.status != CircleStatus.revoked)
        .order_by(TrustCircle.created_at.desc())
    ).scalars().first()
    if circle is None or circle.pairing_code_expires_at < datetime.now(UTC):
        return None
    return circle


def link_guardian_channel(
    db: Session, code: str, channel: CircleChannel, external_id: str
) -> TrustCircle | None:
    """Guardian-side: `/circle <code>` sent from the guardian's own chat —
    registers their channel identity so alerts can be pushed there instead
    of (or in addition to) email."""
    external_id = normalize_external_id(channel, external_id)
    circle = _find_by_code(db, code)
    if circle is None:
        return None
    if circle.elder_channel == channel and circle.elder_external_id == external_id:
        return None  # no self-pairing
    circle.guardian_channel = channel
    circle.guardian_channel_external_id = external_id
    if circle.circle_token is None:
        circle.circle_token = _generate_token()
    if circle.status == CircleStatus.pending:
        circle.status = CircleStatus.active
    db.commit()
    return circle


def complete_web_pairing(
    db: Session, code: str, guardian_name: str, guardian_email: str
) -> TrustCircle | None:
    """Guardian-side: the /trust-circle dashboard form (code + name + email).
    Email is the always-available fallback delivery channel."""
    circle = _find_by_code(db, code)
    if circle is None:
        return None
    circle.guardian_name = guardian_name.strip()[:80]
    circle.guardian_email = guardian_email.strip().lower()[:255]
    if circle.circle_token is None:
        circle.circle_token = _generate_token()
    if circle.status == CircleStatus.pending:
        circle.status = CircleStatus.active
    db.commit()
    return circle


def get_by_token(db: Session, circle_token: str) -> TrustCircle | None:
    return db.execute(
        select(TrustCircle).where(TrustCircle.circle_token == circle_token)
    ).scalars().first()


def revoke(db: Session, circle_token: str) -> bool:
    circle = get_by_token(db, circle_token)
    if circle is None or circle.status == CircleStatus.revoked:
        return False
    circle.status = CircleStatus.revoked
    circle.revoked_at = datetime.now(UTC)
    db.commit()
    return True


def _parse_command(text: str | None) -> tuple[str, str | None] | None:
    if not text:
        return None
    for line in text.splitlines():
        m = _COMMAND_RE.match(line.strip())
        if m:
            code = m.group(1)
            return ("link", code) if code else ("start", None)
    return None


def handle_circle_command(
    db: Session, channel: CircleChannel, external_id: str, text: str | None
) -> str | None:
    """The single entry point every channel adapter calls before running the
    verification pipeline. Returns the reply text if `text` was a circle
    command, or None if this message should fall through to verification."""
    parsed = _parse_command(text)
    if parsed is None:
        return None
    action, code = parsed
    settings = get_settings()
    strings = _load(settings.default_locale).get("circle", {})

    if action == "start":
        circle = start_pairing(db, channel, external_id)
        url = f"{settings.base_url.rstrip('/')}/trust-circle"
        template = strings.get(
            "pair_start_reply",
            'Your Trust Circle code: {code}\n\nGive this to a family member. '
            'They can link up at {url}, or reply here with "/circle {code}" '
            "from their own chat to get alerts sent directly to them.\n\n"
            "This code expires in {ttl} minutes.",
        )
        return template.format_map(_Defaulting({
            "code": circle.pairing_code,
            "url": url,
            "ttl": settings.circle_pairing_code_ttl_minutes,
        }))

    assert code is not None
    circle = link_guardian_channel(db, code, channel, external_id)
    if circle is None:
        return strings.get(
            "pair_invalid_code",
            "That code isn't valid or has expired. Send /circle again for a fresh one.",
        )
    return strings.get(
        "pair_link_confirmed",
        "You're now linked as a Trust Circle guardian. If something risky reaches them, "
        "you'll be alerted here.",
    )
