"""Local SMS WEBHOOK simulator — exercises api/webhooks_sms.py over real
HTTP, the push-based counterpart to scripts/sms_sim.py (which calls
build_reply() in-process, no server or signature check involved). Mirrors
scripts/telegram_webhook_sim.py's approach: POSTs a real, correctly-signed
request to the locally-running backend, so verify_twilio_signature()'s
actual HMAC check runs for real, not just the handler logic behind it.

Two modes, matching the two real routes in api/webhooks_sms.py:

    # Direct: elder texts the bot's own number. Requires the backend
    # running with CHANNEL_SMS_ENABLED=true and a TWILIO_AUTH_TOKEN set
    # (any value — see docs/SETUP_SMS.md).
    python -m scripts.sms_webhook_sim --text "Pay now via UPI scam@okpay"

    # Auto-Guard: a message forwarded from an enrolled phone. Get a
    # guard_token first from the /trust-circle/{token} dashboard (or
    # POST /api/circle/{token}/guard), no Twilio credentials needed at all.
    python -m scripts.sms_webhook_sim --guard-token abc123 --text "Pay now via UPI scam@okpay"
"""
import argparse
import base64
import hashlib
import hmac
import sys

import httpx

from app.config import get_settings


def _twilio_signature(url: str, params: dict[str, str], token: str) -> str:
    data = url + "".join(f"{k}{v}" for k, v in sorted(params.items()))
    return base64.b64encode(hmac.new(token.encode(), data.encode("utf-8"), hashlib.sha1).digest()).decode()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True, help="Plain text message to send")
    parser.add_argument("--from-number", default="+15559990000", help="Sender number in the payload")
    parser.add_argument("--guard-token", help="Auto-Guard token — omit to hit the Direct route instead")
    parser.add_argument("--api-base", default="http://localhost:8000", help="Running backend base URL")
    args = parser.parse_args()

    settings = get_settings()

    if args.guard_token:
        url = f"{args.api_base}/api/webhooks/sms/{args.guard_token}"
        print(f"--- POSTing to the Auto-Guard route (no signature needed) ---\n{url}")
        resp = httpx.post(url, json={"from": args.from_number, "body": args.text}, timeout=30.0)
    else:
        if not settings.channel_sms_enabled:
            print("CHANNEL_SMS_ENABLED is false — the webhook will accept this but do nothing.",
                  file=sys.stderr)
        if not settings.twilio_auth_token:
            print("TWILIO_AUTH_TOKEN is unset — the webhook fails closed and will reject this "
                  "with 403. Set the same value here and on the running server.", file=sys.stderr)
        url = f"{args.api_base}/api/webhooks/sms"
        params = {"From": args.from_number, "To": "+15550100", "Body": args.text, "MessageSid": "SMsimtest"}
        headers = {}
        if settings.twilio_auth_token:
            headers["X-Twilio-Signature"] = _twilio_signature(url, params, settings.twilio_auth_token)
        print(f"--- POSTing to the Direct route (signed: {'yes' if headers else 'no'}) ---\n{url}")
        resp = httpx.post(url, data=params, headers=headers, timeout=30.0)

    print(f"\n--- webhook HTTP response ({resp.status_code}) ---")
    print(resp.text[:500])
    if resp.status_code == 403:
        print("\n(Rejected — signature mismatch or missing token. See docs/SETUP_SMS.md.)", file=sys.stderr)
    elif not args.guard_token:
        print("\n(Reply text isn't in this response — without real Twilio credentials the send "
              "is simulated; check the backend's server log for the composed reply.)", file=sys.stderr)
    else:
        print("\n(Check the guardian's /trust-circle/{token} page for the resulting alert, "
              "if this message was flagged.)", file=sys.stderr)


if __name__ == "__main__":
    main()
