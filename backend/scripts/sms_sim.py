"""Local SMS simulator (Direct channel) — no Twilio account, no network
calls to Twilio, no server needed.

Drives `channels.sms.build_reply()` in-process — the exact function
`api/sim.py`'s `/api/sim/sms` (the `/channels` demo page) also calls, so
this and that page can never drift. The verification pipeline runs for
real against the real seeded registry; only the fact that it "arrived via
SMS" is faked. `sender_external_id` is left unset, same as the demo page —
this can never complete a pairing or fire a real guardian alert; see
scripts/smoke_circle.py for a script that actually exercises those paths
against real TrustCircle rows.

Usage:
    python -m scripts.sms_sim --text "Buy now, guaranteed 40% returns!"
"""
import argparse

from app.channels import sms
from app.db import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True, help="Plain text message to send")
    args = parser.parse_args()

    if sms.is_live():
        print("TWILIO_ACCOUNT_SID/TWILIO_FROM_NUMBER are set, but this script never calls "
              "send_sms() — it only formats the reply build_reply() would produce.")

    print("--- simulated inbound SMS ---")
    print(args.text)

    with SessionLocal() as db:
        reply = sms.build_reply(db, args.text)

    print("\n--- outbound reply (sim: not actually sent) ---")
    print(reply)


if __name__ == "__main__":
    main()
