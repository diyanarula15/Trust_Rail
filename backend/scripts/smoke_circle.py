"""End-to-end smoke for Trust Circle + the SMS channel: pairing, Auto-Guard
enrollment, and both real webhook routes, run against the real dev database
via TestClient — same convention as scripts/smoke.py (a fast pytest suite
can't exercise this: it needs real TrustCircle/CircleAlert rows and a real
signed HTTP request). Exits non-zero on any failure.

The Auto-Guard checks are the actual point of this script: they prove a
message reaching `/api/webhooks/sms/{guard_token}` — the exact route an
Android SMS-forwarder app or a Twilio number would call automatically, with
zero action from the phone's owner — produces a real CircleAlert row a
guardian would see, with no manual "forward this to the bot" step anywhere
in the path. That's the difference between this and the reactive
per-channel bots (WhatsApp/Telegram/email), and it's worth proving directly
rather than trusting the code reading correctly.
"""
import base64
import hashlib
import hmac
import os
import secrets
import sys

# Must happen before `app.main` (and therefore `get_settings()`) is ever
# imported — Settings is process-wide @lru_cache'd, so anything imported
# above this line that touches settings would freeze channel_sms_enabled at
# its default (False) for the rest of this process.
# Deliberately only the auth token, not account_sid/from_number: signature
# verification reads only the token, but is_live() requires all three —
# leaving the other two unset keeps is_live() False, so send_sms() logs
# instead of placing a real (and, with fake credentials, 401-failing) call
# to Twilio's actual API during an automated run.
os.environ.setdefault("CHANNEL_SMS_ENABLED", "true")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "smoke_test_twilio_token")

from fastapi.testclient import TestClient  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.circle import pairing  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CircleChannel, ScamBlacklist  # noqa: E402
from scripts.seed import seed_blacklist  # noqa: E402

SCAM_SMS = (
    "MERIDN IPO allotment confirmed! Pay allotment fee now to "
    "http://rneridianbroking-refunds.top/claim. Pay via UPI meridianrefund@okpay"
)
BENIGN_SMS = "Benchmark indices ended higher today led by banking and IT stocks."


def check(cond: bool, label: str) -> None:
    print(("  ok    " if cond else "  FAIL  ") + label)
    if not cond:
        sys.exit(1)


def _twilio_signature(url: str, params: dict[str, str]) -> str:
    """Same algorithm channels/sms.verify_twilio_signature checks against —
    written out independently here rather than imported, so this script
    also stands as a live cross-check that the two don't quietly drift."""
    token = get_settings().twilio_auth_token
    data = url + "".join(f"{k}{v}" for k, v in sorted(params.items()))
    return base64.b64encode(hmac.new(token.encode(), data.encode("utf-8"), hashlib.sha1).digest()).decode()


def main() -> None:
    client = TestClient(app)

    h = client.get("/healthz").json()
    check(h["db"] and h["redis"], "healthz db+redis")

    # This script's scam-SMS check needs the FXROAD-DEMO blacklist fixture to
    # exist. Seeded directly here (matching scripts/smoke.py's own pattern of
    # seeding exactly what it depends on) rather than assumed present — the
    # other smoke scripts wipe the whole demo world including this fixture,
    # and this script running straight after one of those, before a reseed,
    # is exactly how the first draft of this test went red on a correct
    # LIKELY_FAKE verdict that just had no campaign attached anymore.
    with SessionLocal() as db:
        exists = db.execute(
            select(ScamBlacklist.id).where(ScamBlacklist.campaign == "FXROAD-DEMO")
        ).first()
        if exists is None:
            seed_blacklist(db)
            db.commit()

    # ---- pairing: elder side (direct DB call — every channel adapter does
    # exactly this internally regardless of transport) + guardian side (the
    # real HTTP endpoint) ----
    print("smoke_circle: elder starts pairing, guardian completes it over HTTP")
    # A fresh identity every run, deliberately: start_pairing() reuses any
    # existing pending/active circle for the same elder identity rather than
    # creating a duplicate (correct product behavior — a real elder who
    # re-sends /circle shouldn't get a second circle). That's exactly what
    # bit this script on its second run: reusing a fixed number meant run 2
    # inherited run 1's already-guard-enabled circle instead of starting
    # clean, and "Auto-Guard not enabled by default" failed for a reason
    # that had nothing to do with the code under test.
    elder_number = f"+9198765{secrets.randbelow(90000) + 10000}"
    with SessionLocal() as db:
        circle = pairing.start_pairing(db, CircleChannel.sms, elder_number)
        code = circle.pairing_code

    r = client.post(
        "/api/circle/pair/complete",
        json={"code": code, "guardian_name": "Smoke Guardian", "guardian_email": "guardian@smoke.example"},
    ).json()
    check(r["ok"] and r["data"]["circle_token"], "guardian pairing completed")
    circle_token = r["data"]["circle_token"]

    status = client.get(f"/api/circle/{circle_token}").json()["data"]
    check(status["status"] == "active", "circle active immediately after pairing")
    check(status["guard_enabled"] is False, "Auto-Guard not enabled by default")
    check(len(status["alerts"]) == 0, "no alerts yet")

    # ---- Auto-Guard: enable, then fire real messages at the real webhook ----
    print("smoke_circle: enable Auto-Guard")
    r = client.post(f"/api/circle/{circle_token}/guard").json()
    check(r["ok"] and r["data"]["guard_token"], "guard token issued")
    guard_token = r["data"]["guard_token"]
    check(r["data"]["webhook_url"].endswith(f"/api/webhooks/sms/{guard_token}"), "webhook url shape correct")

    r2 = client.post(f"/api/circle/{circle_token}/guard").json()
    check(r2["data"]["guard_token"] == guard_token, "re-enabling is idempotent, doesn't rotate the token")

    print("smoke_circle: a scam text arrives on the elder's phone (nobody clicked anything)")
    r = client.post(f"/api/webhooks/sms/{guard_token}", json={"from": "+15559990001", "body": SCAM_SMS}).json()
    check(r["ok"], "guard webhook accepted the message")

    status = client.get(f"/api/circle/{circle_token}").json()["data"]
    check(len(status["alerts"]) == 1, "exactly one alert landed from the scam text")
    alert = status["alerts"][0]
    check(alert["verdict"] == "LIKELY_FAKE", f"alert verdict is LIKELY_FAKE (got {alert['verdict']})")
    check(alert["campaign"] == "FXROAD-DEMO", f"alert carries the campaign name (got {alert['campaign']!r})")
    check(alert["delivered_via"] == "email", "delivered via the guardian's email (no bot channel linked)")

    print("smoke_circle: a benign text arrives — must NOT alert anyone")
    client.post(f"/api/webhooks/sms/{guard_token}", json={"from": "+15559990002", "body": BENIGN_SMS})
    status = client.get(f"/api/circle/{circle_token}").json()["data"]
    check(len(status["alerts"]) == 1, "still exactly one alert — the benign text did not trigger a second")

    print("smoke_circle: an unrecognized guard token is rejected without crashing")
    r = client.post("/api/webhooks/sms/not-a-real-token", json={"from": "+1555", "body": SCAM_SMS})
    check(r.status_code == 200, "unknown guard token still returns 200 (never a 500)")
    check(r.json()["ok"] is True and "ignored" in r.json()["data"], "unknown guard token explicitly ignored")

    print("smoke_circle: disabling Auto-Guard revokes the old URL immediately")
    r = client.post(f"/api/circle/{circle_token}/guard/disable").json()
    check(r["ok"] and r["data"]["guard_enabled"] is False, "guard disabled")
    client.post(f"/api/webhooks/sms/{guard_token}", json={"from": "+15559990003", "body": SCAM_SMS})
    status = client.get(f"/api/circle/{circle_token}").json()["data"]
    check(len(status["alerts"]) == 1, "scam sent to the disabled URL produced no new alert")
    check(status["guard_enabled"] is False, "guard_enabled correctly false in status")

    print("smoke_circle: regenerating issues a different token")
    client.post(f"/api/circle/{circle_token}/guard")  # re-enable
    r = client.post(f"/api/circle/{circle_token}/guard/regenerate").json()
    new_token = r["data"]["guard_token"]
    check(new_token != guard_token, "regenerate produced a fresh token")

    # ---- direct/two-way SMS: elder texts the bot's OWN number, real Twilio
    # signature required and genuinely verified ----
    print("smoke_circle: direct SMS webhook — real Twilio-shaped signature required")
    direct_elder = f"+9198766{secrets.randbelow(90000) + 10000}"
    params = {"From": direct_elder, "To": "+15550100", "Body": SCAM_SMS, "MessageSid": "SMsmoketest1"}
    url = str(client.base_url) + "/api/webhooks/sms"
    r = client.post("/api/webhooks/sms", data=params)  # no signature at all
    check(r.status_code == 403, "direct webhook rejects an unsigned request")

    sig = _twilio_signature(url, params)
    r = client.post("/api/webhooks/sms", data=params, headers={"X-Twilio-Signature": sig})
    check(r.status_code == 200, "correctly signed direct webhook request accepted")

    with SessionLocal() as db:
        found = pairing._find_for_elder(db, CircleChannel.sms, direct_elder)
        check(found is None, "no circle exists yet for this number (nothing paired) — sanity check only")

    print("SMOKE_CIRCLE PASS")
    print()
    print("!" * 72)
    print("This script created real TrustCircle/CircleAlert rows in the dev DB")
    print(f"(elder {elder_number}, guardian guardian@smoke.example). Harmless to")
    print("leave, or clear with a normal `make demo-reset`.")
    print("!" * 72)


if __name__ == "__main__":
    main()
