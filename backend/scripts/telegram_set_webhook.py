"""One-off: register a real Telegram webhook for this bot token, pointing at
a public URL (e.g. an ngrok/cloudflared tunnel, or a real deployment). See
docs/SETUP_TELEGRAM.md.

Mutually exclusive with scripts/telegram_poll.py — once a webhook is set,
getUpdates (what the poller uses) will 409 until you call
`python -m scripts.telegram_delete_webhook` or set a new webhook elsewhere.

Usage:
    python -m scripts.telegram_set_webhook https://your-tunnel.example/api/webhooks/telegram
"""
import sys

from app.channels import telegram
from app.config import get_settings


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.telegram_set_webhook <public-url>", file=sys.stderr)
        sys.exit(1)

    settings = get_settings()
    if not settings.telegram_bot_token:
        print("TELEGRAM_BOT_TOKEN is unset — set it in .env first.", file=sys.stderr)
        sys.exit(1)
    if not settings.telegram_webhook_secret:
        print("TELEGRAM_WEBHOOK_SECRET is unset — the webhook route fails closed without one. "
              "Set any string value in .env before registering.", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    result = telegram.set_webhook(url, settings.telegram_webhook_secret)
    print(result)
    if result.get("ok"):
        print(f"\nWebhook registered: {url}")
        print("Remember: scripts/telegram_poll.py can't run at the same time as this webhook.")


if __name__ == "__main__":
    main()
