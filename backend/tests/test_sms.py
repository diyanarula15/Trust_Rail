"""SMS channel: signature verification and reply formatting.

Pure logic only — no DB, matching this test suite's existing convention
(pipeline/verdict logic tested directly, DB-touching integration checks live
in scripts/smoke*.py against the real dev database). The webhook routes and
the full pairing -> Auto-Guard -> alert flow are covered by
scripts/smoke_circle.py instead, since they need real TrustCircle rows.
"""
import base64
import hashlib
import hmac

import pytest

from app.channels import sms
from app.config import get_settings


@pytest.fixture(autouse=True)
def _twilio_env(monkeypatch: pytest.MonkeyPatch):
    """A consistent, known auth token for every test in this file, cleared
    afterward so it can't leak into other tests via the cached settings."""
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_auth_token_123")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15550100")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _real_twilio_signature(url: str, params: dict[str, str], token: str) -> str:
    """Independently reproduces Twilio's documented signing algorithm — a
    second implementation, not a call into the code under test, so this
    actually proves verify_twilio_signature() is correct rather than
    checking it against itself."""
    data = url + "".join(f"{k}{v}" for k, v in sorted(params.items()))
    digest = hmac.new(token.encode(), data.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


class TestTwilioSignature:
    URL = "https://trustrail.example/api/webhooks/sms"
    PARAMS = {"From": "+919812345678", "To": "+15550100", "Body": "hello", "MessageSid": "SM123"}

    def test_valid_signature_accepted(self) -> None:
        sig = _real_twilio_signature(self.URL, self.PARAMS, "test_auth_token_123")
        assert sms.verify_twilio_signature(self.URL, self.PARAMS, sig) is True

    def test_wrong_token_rejected(self) -> None:
        sig = _real_twilio_signature(self.URL, self.PARAMS, "a_completely_different_token")
        assert sms.verify_twilio_signature(self.URL, self.PARAMS, sig) is False

    def test_tampered_param_rejected(self) -> None:
        """Signature computed over the real body, checked against a payload
        where an attacker changed one field after the fact — the actual
        threat this check exists to catch."""
        sig = _real_twilio_signature(self.URL, self.PARAMS, "test_auth_token_123")
        tampered = {**self.PARAMS, "Body": "send money now"}
        assert sms.verify_twilio_signature(self.URL, tampered, sig) is False

    def test_tampered_url_rejected(self) -> None:
        sig = _real_twilio_signature(self.URL, self.PARAMS, "test_auth_token_123")
        assert sms.verify_twilio_signature(self.URL + "/evil", self.PARAMS, sig) is False

    def test_missing_signature_rejected(self) -> None:
        assert sms.verify_twilio_signature(self.URL, self.PARAMS, None) is False

    def test_missing_signature_rejected_even_with_no_params(self) -> None:
        assert sms.verify_twilio_signature(self.URL, {}, None) is False

    def test_no_auth_token_configured_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same posture as WhatsApp's HMAC check and Telegram's shared
        secret: absent configuration means reject everything, never trust
        by default."""
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
        get_settings.cache_clear()
        sig = _real_twilio_signature(self.URL, self.PARAMS, "")
        assert sms.verify_twilio_signature(self.URL, self.PARAMS, sig) is False


class TestIsLive:
    def test_live_when_fully_configured(self) -> None:
        assert sms.is_live() is True

    def test_not_live_missing_from_number(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TWILIO_FROM_NUMBER", "")
        get_settings.cache_clear()
        assert sms.is_live() is False


class TestFormatReply:
    def test_includes_headline_body_reason_and_link(self) -> None:
        card = {
            "plain_headline": "This looks like a scam",
            "plain_body": "Do not pay anyone.",
            "plain_reason_strings": ["It contains a suspicious link."],
            "buttons": [{"kind": "sebi_check", "label": "Check", "url": "/some/path"}],
        }
        text = sms._format_reply(card)
        assert "This looks like a scam" in text
        assert "Do not pay anyone." in text
        assert "It contains a suspicious link." in text
        assert "/some/path" in text  # absolutized by card_buttons()

    def test_tolerates_missing_optional_fields(self) -> None:
        card = {"plain_headline": "Nothing official here", "plain_body": "No claim made."}
        text = sms._format_reply(card)
        assert "Nothing official here" in text
