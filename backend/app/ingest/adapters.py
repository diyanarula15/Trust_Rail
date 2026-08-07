"""Feed-format adapters: whatever a source calls its fields, out comes a FeedItem.

Two are implemented because they are the two intake paths a real deployment
would actually use, and both already exist as infrastructure:

  * exchange filings — corporate announcements as exchanges already publish
    them (scrip code, subject, category, attachment)
  * DLT SMS — the TRAI Distributed Ledger registry that already governs
    commercial SMS in India, where every sender header and message template
    is pre-registered before a single message can be sent

Neither invents a new obligation for issuers. That is the whole argument for
this being a rail rather than another portal: the content is already being
filed and already being registered; it just isn't being signed or made
verifiable afterwards.
"""
from __future__ import annotations

from typing import Any

from app.ingest.sources import FeedItem, parse_when

# --- exchange filings ----------------------------------------------------

# Category → (channel, impact). Exchanges already classify announcements;
# this maps their vocabulary onto ours rather than asking anyone to re-tag.
_EXCHANGE_CATEGORY: dict[str, tuple[str, str]] = {
    "board_meeting": ("filing", "market_moving"),
    "financial_results": ("filing", "market_moving"),
    "corporate_action": ("filing", "market_moving"),
    "acquisition": ("filing", "market_moving"),
    "disclosure": ("filing", "standard"),
    "compliance": ("filing", "standard"),
    "general": ("filing", "standard"),
}


def from_exchange_filing(raw: dict[str, Any]) -> FeedItem | None:
    """An exchange announcement row → FeedItem.

    Accepts the field names exchanges commonly use, with fallbacks, so
    pointing this at a real feed is mostly a matter of confirming key names.
    """
    external_id = str(
        raw.get("id") or raw.get("announcement_id") or raw.get("seq_id") or ""
    ).strip()
    entity_hint = str(
        raw.get("scrip_code") or raw.get("symbol") or raw.get("company") or raw.get("entity") or ""
    ).strip()
    subject = str(raw.get("subject") or raw.get("headline") or raw.get("title") or "").strip()
    if not external_id or not entity_hint or not subject:
        return None

    category = str(raw.get("category") or raw.get("type") or "general").strip().lower()
    channel, impact = _EXCHANGE_CATEGORY.get(category, ("filing", "standard"))

    return FeedItem(
        external_id=external_id,
        entity_hint=entity_hint,
        title=subject,
        channel=channel,
        impact=impact,
        body_text=(raw.get("body") or raw.get("text") or None),
        document_path=raw.get("attachment_path"),
        document_url=raw.get("attachment_url") or raw.get("pdf_url"),
        published_at=parse_when(raw.get("published_at") or raw.get("submitted_at")),
        raw=raw,
    )


# --- DLT SMS gateway -----------------------------------------------------

def from_dlt_sms(raw: dict[str, Any]) -> FeedItem | None:
    """A DLT-registered SMS template → FeedItem.

    Under TRAI's DLT regime every commercial sender header and message
    template is registered before use, so the authoritative wording already
    exists in a registry. Ingesting it means an SMS a person actually
    receives can be checked against the template its sender registered.

    Template variables ({#var#}) are kept verbatim: the registered template
    is the thing being attested, and the matcher's tolerance handles the
    filled-in values at verification time.
    """
    external_id = str(raw.get("template_id") or raw.get("id") or "").strip()
    header = str(raw.get("header") or raw.get("sender_id") or raw.get("pe_header") or "").strip()
    body = str(raw.get("template") or raw.get("content") or raw.get("body") or "").strip()
    if not external_id or not header or not body:
        return None

    return FeedItem(
        external_id=external_id,
        entity_hint=header,                       # resolved via entity_sms_headers
        title=str(raw.get("template_name") or f"Registered SMS template {external_id}"),
        channel="sms",
        impact="standard",
        body_text=body,
        published_at=parse_when(raw.get("registered_at") or raw.get("approved_at")),
        raw=raw,
    )


ADAPTERS = {
    "exchange_filings": from_exchange_filing,
    "dlt_sms": from_dlt_sms,
}
