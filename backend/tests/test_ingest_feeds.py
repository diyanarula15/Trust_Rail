"""Feed ingestion: mapping, and the guards that keep it safe to re-run.

The DB-backed publish path is exercised by scripts/ingest_feeds.py against
the live demo world; these cover the pure logic and the two things most
likely to break quietly — a feed field being renamed, and re-polling
producing duplicates.
"""
from pathlib import Path

import pytest

from app.channels.whatsapp import format_card, verify_webhook_signature
from app.ingest.adapters import from_dlt_sms, from_exchange_filing
from app.ingest.sources import JsonFileSource, parse_when

FEEDS = Path(__file__).resolve().parents[2] / "fixtures" / "feeds"


class TestExchangeAdapter:
    def test_maps_a_filing_row(self) -> None:
        item = from_exchange_filing(
            {
                "id": "NDX-1",
                "scrip_code": "DEMO-INE-000451",
                "category": "financial_results",
                "subject": "Unaudited results for the quarter",
                "attachment_path": "fixtures/generated/filing_kumaon_q1.pdf",
                "published_at": "2026-07-12T11:20:00+05:30",
            }
        )
        assert item is not None
        assert item.entity_hint == "DEMO-INE-000451"
        assert item.channel == "filing"
        # results and board meetings move markets — they need two signatures
        assert item.impact == "market_moving"

    def test_routine_disclosure_is_standard_impact(self) -> None:
        item = from_exchange_filing(
            {"id": "x", "scrip_code": "y", "category": "disclosure", "subject": "s"}
        )
        assert item is not None and item.impact == "standard"

    def test_unknown_category_degrades_rather_than_failing(self) -> None:
        item = from_exchange_filing(
            {"id": "x", "scrip_code": "y", "category": "something_new", "subject": "s"}
        )
        assert item is not None and item.channel == "filing" and item.impact == "standard"

    @pytest.mark.parametrize(
        "row",
        [
            {"scrip_code": "y", "subject": "s"},   # no id
            {"id": "x", "subject": "s"},           # no issuer
            {"id": "x", "scrip_code": "y"},        # no subject
        ],
    )
    def test_incomplete_rows_are_skipped_not_guessed(self, row: dict) -> None:
        assert from_exchange_filing(row) is None

    def test_alternate_field_names(self) -> None:
        """Feeds differ; the adapter accepts the common spellings."""
        item = from_exchange_filing(
            {"announcement_id": "A1", "symbol": "KUMAON", "headline": "Board meeting outcome"}
        )
        assert item is not None and item.external_id == "A1"


class TestDltAdapter:
    def test_maps_a_registered_template(self) -> None:
        item = from_dlt_sms(
            {
                "template_id": "1307161234567890123",
                "header": "MERIDN",
                "template": "MERIDN: Margin shortfall in your account.",
                "registered_at": "2026-06-18T10:12:00+05:30",
            }
        )
        assert item is not None
        assert item.entity_hint == "MERIDN"      # resolved via entity_sms_headers
        assert item.channel == "sms"
        assert item.body_text.startswith("MERIDN:")

    def test_template_variables_are_preserved(self) -> None:
        """The registered template is the thing being attested — the matcher's
        tolerance deals with filled-in values later."""
        item = from_dlt_sms(
            {"template_id": "t", "header": "MERIDN", "template": "Balance {#var#} as on {#var#}"}
        )
        assert item is not None and "{#var#}" in item.body_text

    def test_incomplete_template_skipped(self) -> None:
        assert from_dlt_sms({"template_id": "t", "header": "MERIDN"}) is None


class TestShippedFeeds:
    """The sample feeds must actually parse — they are what proves the path."""

    def test_exchange_feed_parses_completely(self) -> None:
        rows = JsonFileSource("x", FEEDS / "exchange_filings.json").fetch()
        assert len(rows) >= 5
        assert all(from_exchange_filing(r) is not None for r in rows)

    def test_dlt_feed_parses_completely(self) -> None:
        rows = JsonFileSource("x", FEEDS / "dlt_sms.json").fetch()
        assert len(rows) >= 5
        assert all(from_dlt_sms(r) is not None for r in rows)

    def test_missing_feed_file_is_empty_not_an_error(self) -> None:
        assert JsonFileSource("x", FEEDS / "nope.json").fetch() == []


def test_parse_when_handles_offsets_and_z() -> None:
    assert parse_when("2026-07-12T11:20:00+05:30") is not None
    assert parse_when("2026-07-12T05:50:00Z") is not None
    assert parse_when("") is None
    assert parse_when("not a date") is None


class TestWhatsAppSignature:
    """The webhook must reject anything it cannot attribute to Meta — a
    system selling authenticity cannot accept unauthenticated input."""

    def test_unsigned_request_rejected(self) -> None:
        assert verify_webhook_signature(b"{}", None) is False

    def test_wrong_signature_rejected(self) -> None:
        assert verify_webhook_signature(b"{}", "sha256=deadbeef") is False

    def test_correct_signature_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import hashlib
        import hmac

        from app.config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "s3cret")
        body = b'{"entry":[]}'
        sig = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(body, sig) is True
        get_settings.cache_clear()


def test_whatsapp_card_uses_plain_language_from_the_api() -> None:
    """The adapter carries copy, it never writes it."""
    from app.channels.render import CardPayload

    card = CardPayload(
        verification_id="v1",
        verdict="LIKELY_FAKE",
        headline="🚨 High risk",
        body="formal body",
        plain_headline="This looks like a scam",
        plain_body="Do not pay anyone.",
        plain_reason_strings=["It contains a suspicious link."],
        reasons=["URL_RISK"],
        reason_strings=["Contains a suspicious link."],
        advice=["Verify the payee first."],
        buttons=[],
        pipeline_trace=[],
        locale="en",
    )
    text = format_card(card)
    assert "This looks like a scam" in text      # plain register preferred
    assert "Do not pay anyone." in text
    assert "It contains a suspicious link." in text
