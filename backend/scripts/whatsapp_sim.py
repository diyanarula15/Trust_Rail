"""Local WhatsApp Cloud API webhook simulator — no Meta Business account,
no public URL. Builds a byte-accurate fake webhook payload (Meta's real
`entry[].changes[].value.messages[]` shape) referencing a real local file,
computes a real X-Hub-Signature-256 if WHATSAPP_APP_SECRET is set (so the
signature-verification code path runs for real), and POSTs it over real HTTP
to the locally-running backend. The verification pipeline runs for real
against the real seeded registry; only the fact that this came from Meta is
faked.

Requires the backend to be running (uvicorn) and CHANNEL_WHATSAPP_ENABLED=true.

Usage:
    python -m scripts.whatsapp_sim --file ../assets_input/image1.jpg
    python -m scripts.whatsapp_sim --text "Buy now, guaranteed returns!"
"""
import argparse
import hashlib
import hmac
import json
import sys
from pathlib import Path

import httpx

from app.config import get_settings


def _fake_body(*, file_path: str | None, text: str | None, caption: str | None) -> dict:
    message: dict = {"from": "919990001234", "id": "wamid.sim", "timestamp": "0"}
    if text is not None:
        message["type"] = "text"
        message["text"] = {"body": text}
    else:
        p = Path(file_path)
        suffix = p.suffix.lower()
        mtype = {
            ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image",
            ".mp4": "video",
        }.get(suffix, "document")
        message["type"] = mtype
        node = {"id": "sim-media-id", "mime_type": "application/octet-stream"}
        if caption:
            node["caption"] = caption
        if mtype == "document":
            node["filename"] = p.name
        message[mtype] = node
        # Sim-only escape hatch: a real Meta payload never carries this key.
        # channels/whatsapp.py reads bytes from here instead of calling the
        # Graph API (there's no real media_id to resolve against).
        message["_sim_local_path"] = str(p)

    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "sim-waba-id",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15550001111", "phone_number_id": "sim"},
                    "contacts": [{"profile": {"name": "Sim"}, "wa_id": message["from"]}],
                    "messages": [message],
                },
                "field": "messages",
            }],
        }],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to an image/video/document to forward")
    group.add_argument("--text", help="Plain text message to forward")
    parser.add_argument("--caption", help="Caption to attach to a --file message")
    parser.add_argument("--api-base", default="http://localhost:8000", help="Running backend base URL")
    args = parser.parse_args()

    if args.file and not Path(args.file).exists():
        print(f"No such file: {args.file}", file=sys.stderr)
        sys.exit(1)

    settings = get_settings()
    if not settings.channel_whatsapp_enabled:
        print("CHANNEL_WHATSAPP_ENABLED is false — the webhook will accept this but do nothing. "
              "Set it to true in .env (leave WHATSAPP_TOKEN empty to stay in sim mode).", file=sys.stderr)

    body = _fake_body(file_path=args.file, text=args.text, caption=args.caption)
    # _sim_local_path is a testing-only field — strip it before computing the
    # signature/printing, since a real Meta payload would never include it
    # and we want the signature to cover exactly what's sent.
    raw = json.dumps(body).encode()

    headers = {"Content-Type": "application/json"}
    if settings.whatsapp_app_secret:
        sig = hmac.new(settings.whatsapp_app_secret.encode(), raw, hashlib.sha256).hexdigest()
        headers["X-Hub-Signature-256"] = f"sha256={sig}"

    print("--- simulated inbound webhook POST body ---")
    print(json.dumps(body, indent=2))

    resp = httpx.post(f"{args.api_base}/api/webhooks/whatsapp", content=raw, headers=headers, timeout=30.0)
    resp.raise_for_status()
    result = resp.json()

    print("\n--- webhook HTTP response ---")
    print(json.dumps(result, indent=2))
    if not result.get("handled"):
        print("\n(Nothing handled — is CHANNEL_WHATSAPP_ENABLED=true and is the backend running?)",
              file=sys.stderr)
    else:
        print("\n(Reply text isn't in this response — without real WHATSAPP_TOKEN/"
              "WHATSAPP_PHONE_NUMBER_ID the send is simulated; check the backend's "
              "server log for the composed reply.)", file=sys.stderr)


if __name__ == "__main__":
    main()
