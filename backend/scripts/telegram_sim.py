"""Local Telegram simulator — no bot token, no network calls to Telegram.

Builds a realistic fake Update dict (the exact shape getUpdates would return)
referencing a real local file or a text message, then drives it through
`channels/telegram.dispatch_update` — the same function the real long-poll
loop (`scripts/telegram_poll.py`) would call. The verification pipeline runs
for real against the real seeded registry; only the Telegram transport
(receiving the update, sending the reply) is faked.

Usage:
    python -m scripts.telegram_sim --file ../assets_input/filing1.pdf
    python -m scripts.telegram_sim --text "Buy now, guaranteed 40% returns!"
"""
import argparse
import json
import sys
from pathlib import Path

from app.channels import telegram
from app.db import SessionLocal


def _fake_update(update_id: int, *, file_path: str | None, text: str | None, caption: str | None) -> dict:
    chat = {"id": 999_000_001, "type": "private", "first_name": "Sim"}
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
    args = parser.parse_args()

    if args.file and not Path(args.file).exists():
        print(f"No such file: {args.file}", file=sys.stderr)
        sys.exit(1)

    if telegram.is_live():
        print("TELEGRAM_BOT_TOKEN is set — this would send for real. "
              "Unset it (or use scripts.telegram_poll) to go live.", file=sys.stderr)

    update = _fake_update(1, file_path=args.file, text=args.text, caption=args.caption)
    print("--- simulated inbound update ---")
    print(json.dumps({k: v for k, v in update["message"].items() if k != "_sim_local_path"}, indent=2))

    with SessionLocal() as db:
        result = telegram.dispatch_update(update, db)

    print("\n--- outbound reply (sim: logged, not sent) ---")
    print(result["text"] if result else "(no reply)")
    if result and result.get("reply_markup"):
        print(json.dumps(result["reply_markup"], indent=2))


if __name__ == "__main__":
    main()
