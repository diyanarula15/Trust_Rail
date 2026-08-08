"""One-off: unregister this bot's webhook, so scripts/telegram_poll.py's
getUpdates can be used again (the two are mutually exclusive at the
Telegram API level). scripts/telegram_poll.py already calls this itself at
startup — this script exists for switching back to polling without also
starting the poller (e.g. while debugging).

Usage:
    python -m scripts.telegram_delete_webhook
"""
from app.channels import telegram
from app.config import get_settings


def main() -> None:
    if not get_settings().telegram_bot_token:
        print("TELEGRAM_BOT_TOKEN is unset — nothing to do.")
        return
    telegram.delete_webhook()
    print("Webhook deleted (or none was set). getUpdates is now usable again.")


if __name__ == "__main__":
    main()
