"""Small helpers shared by every channel adapter (Telegram, WhatsApp, email)."""
from typing import Any

from app.config import get_settings


def absolutize(url: str) -> str:
    """render.py's Button.url is a relative path (e.g. "/c/{token}") because
    it's meant to be rendered by the Next.js frontend. Every non-web channel
    needs the full URL instead. Leaves "#" (the un-set SEBI_CHECK_URL
    placeholder) and already-absolute URLs untouched."""
    if not url or url == "#" or url.startswith(("http://", "https://")):
        return url
    return get_settings().base_url.rstrip("/") + url


def card_buttons(card: dict[str, Any]) -> list[dict[str, str]]:
    """`card["buttons"]` (from run_verification's rendered dict) with every
    url absolutized, and any button with nothing real to link to dropped:
    an empty url (render.py's "expand_trace", a pure web-UI accordion
    trigger with no chat/email equivalent) or the literal "#" placeholder
    (SEBI_CHECK_URL is unset in this prototype — a dead link is worse than
    no button; the same reminder is already in the card's `advice` text)."""
    return [
        {**b, "url": absolutize(b["url"])}
        for b in card.get("buttons", [])
        if b.get("url") and b["url"] != "#"
    ]
