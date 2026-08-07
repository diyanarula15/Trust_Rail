"""Real IMAP poll loop + SMTP reply. Not run today (no real mailbox
configured); see docs/SETUP_EMAIL.md for how to set one up (e.g. a Gmail app
password) and go live.

    python -m scripts.email_poll
"""
import logging
import time

from app.channels import email_channel
from app.config import get_settings
from app.db import SessionLocal

logger = logging.getLogger(__name__)


def _poll_once() -> None:
    imap = email_channel.connect_imap()
    try:
        for uid, raw in email_channel.fetch_unseen(imap):
            try:
                with SessionLocal() as db:
                    email_channel.handle_raw_message(raw, db)
            except Exception:
                logger.exception("message uid %s failed", uid)
            finally:
                # Mark seen in a finally, after attempting to handle it — this
                # is the ack mechanism (mirrors Telegram's offset-advance): a
                # crash mid-handling must not leave the message stuck
                # UNSEEN-and-retried forever, but it also must not be marked
                # seen before we've tried, or a crash between fetch and
                # handling would silently drop it.
                email_channel.mark_seen(imap, uid)
    finally:
        imap.logout()


def main() -> None:
    settings = get_settings()
    if not settings.channel_email_enabled or not settings.email_imap_host:
        print("Email channel disabled or EMAIL_IMAP_HOST unset — see docs/SETUP_EMAIL.md")
        return

    print("Email poller started. Ctrl+C to stop.")
    while True:
        try:
            _poll_once()
        except Exception:
            logger.exception("poll cycle failed; retrying after interval")
        time.sleep(settings.email_poll_interval_seconds)


if __name__ == "__main__":
    main()
