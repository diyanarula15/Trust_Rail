"""Real Telegram long-poll loop. Needs no public URL/webhook — getUpdates is
pull-based, which is why Telegram (unlike WhatsApp) can go live with nothing
more than a bot token. Not run today (no real token configured); see
docs/SETUP_TELEGRAM.md for how to get one and go live.

    python -m scripts.telegram_poll
"""
import logging
import time

from app.channels import telegram
from app.config import get_settings
from app.db import SessionLocal, get_redis

logger = logging.getLogger(__name__)
_OFFSET_KEY = "trustrail:telegram:offset"


def _load_offset(redis) -> int | None:
    raw = redis.get(_OFFSET_KEY)
    return int(raw) if raw is not None else None


def _save_offset(redis, offset: int) -> None:
    redis.set(_OFFSET_KEY, offset)


def main() -> None:
    settings = get_settings()
    if not settings.channel_telegram_enabled or not settings.telegram_bot_token:
        print("Telegram channel disabled or TELEGRAM_BOT_TOKEN unset — see docs/SETUP_TELEGRAM.md")
        return

    telegram.delete_webhook()
    redis = get_redis()
    offset = _load_offset(redis)
    print("Telegram poller started. Ctrl+C to stop.")

    while True:
        try:
            updates = telegram.get_updates(offset, timeout=30)
        except Exception:
            logger.exception("getUpdates failed; retrying in 5s")
            time.sleep(5)
            continue

        for update in updates:
            try:
                with SessionLocal() as db:
                    telegram.dispatch_update(update, db)
            except Exception:
                logger.exception("update %s failed", update.get("update_id"))
            finally:
                # Advance unconditionally, even on failure — otherwise a
                # single bad update wedges the poller forever (Telegram
                # keeps re-serving the lowest un-acked update).
                offset = update["update_id"] + 1
                _save_offset(redis, offset)


if __name__ == "__main__":
    main()
