"""Local Telegram WEBHOOK simulator — exercises api/webhooks_telegram.py
over real HTTP, the push-based counterpart to scripts/telegram_sim.py (which
calls dispatch_update() in-process, no server or secret-token check
involved). Mirrors scripts/whatsapp_sim.py's approach: builds a realistic
fake Update, POSTs it for real to the locally-running backend, and includes
a real X-Telegram-Bot-Api-Secret-Token header if TELEGRAM_WEBHOOK_SECRET is
set — so the secret-verification code path in
channels/telegram.verify_webhook_secret runs for real, not just the handler
logic behind it.

Requires the backend to be running (uvicorn) and CHANNEL_TELEGRAM_ENABLED=true.
TELEGRAM_WEBHOOK_SECRET must be set (it fails closed with none configured,
same posture as WhatsApp's signature check — see docs/SETUP_TELEGRAM.md).

Usage:
    python -m scripts.telegram_webhook_sim --file ../fixtures/generated/filing_kumaon_q1.pdf
    python -m scripts.telegram_webhook_sim --text "Buy now, guaranteed 40% returns!"
"""
import argparse
import json
import sys
from pathlib import Path

import httpx

from app.config import get_settings


def _fake_update(update_id: int, *, file_path: str | None, text: str | None, caption: str | None) -> dict:
    chat = {"id": 999_000_002, "type": "private", "first_name": "Sim"}
    message: dict = {
        "message_id": update_id,
        "date": 0,
        "chat": chat,
        "from": {"id": chat["id"], "is_bot": False, "first_name": "Sim"},
    }
    if text is not None:
        message["text"] = text
        return {"update_id": update_id, "message": message}

    assert file_path is not None
    p = Path(file_path)
    suffix = p.suffix.lower()
    if caption:
        message["caption"] = caption
    if suffix in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        message["photo"] = [{"file_id": "sim", "file_size": p.stat().st_size, "width": 0, "height": 0}]
    elif suffix == ".mp4":
        message["video"] = {"file_id": "sim", "file_size": p.stat().st_size}
    else:
        message["document"] = {"file_id": "sim", "file_size": p.stat().st_size, "file_name": p.name}
    # Sim-only escape hatch: a real Telegram payload never carries this key.
    # dispatch_update() reads bytes from here instead of calling getFile.
    message["_sim_local_path"] = str(p)
    return {"update_id": update_id, "message": message}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to an image/video/pdf/document to forward")
    group.add_argument("--text", help="Plain text message to forward")
    parser.add_argument("--caption", help="Caption to attach to a --file message (claimed_sender_text)")
    parser.add_argument("--api-base", default="http://localhost:8000", help="Running backend base URL")
    args = parser.parse_args()

    if args.file and not Path(args.file).exists():
        print(f"No such file: {args.file}", file=sys.stderr)
        sys.exit(1)

    settings = get_settings()
    if not settings.channel_telegram_enabled:
        print("CHANNEL_TELEGRAM_ENABLED is false — the webhook will accept this but do nothing.",
              file=sys.stderr)
    if not settings.telegram_webhook_secret:
        print("TELEGRAM_WEBHOOK_SECRET is unset — the webhook fails closed and will reject this "
              "with 403. Set the same value here and on the running server.", file=sys.stderr)

    update = _fake_update(1, file_path=args.file, text=args.text, caption=args.caption)
    printable = {**update, "message": {k: v for k, v in update["message"].items() if k != "_sim_local_path"}}
    print("--- simulated inbound webhook POST body ---")
    print(json.dumps(printable, indent=2))

    headers = {"Content-Type": "application/json"}
    if settings.telegram_webhook_secret:
        headers["X-Telegram-Bot-Api-Secret-Token"] = settings.telegram_webhook_secret

    resp = httpx.post(f"{args.api_base}/api/webhooks/telegram", json=update, headers=headers, timeout=30.0)
    resp.raise_for_status()
    result = resp.json()

    print("\n--- webhook HTTP response ---")
    print(json.dumps(result, indent=2))
    if not result.get("data", {}).get("handled"):
        print("\n(Nothing handled — check CHANNEL_TELEGRAM_ENABLED and TELEGRAM_WEBHOOK_SECRET "
              "on the running server.)", file=sys.stderr)
    else:
        print("\n(Reply text isn't in this response — without a real TELEGRAM_BOT_TOKEN the send "
              "is simulated; check the backend's server log for the composed reply.)", file=sys.stderr)


if __name__ == "__main__":
    main()
