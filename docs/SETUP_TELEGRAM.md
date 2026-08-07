# Telegram channel

**Ships simulated today.** No bot token is configured, so nothing polls a
real Telegram server. Test it right now with:

```
cd backend
.venv/Scripts/python.exe -m scripts.telegram_sim --file ../assets_input/filing1.pdf
.venv/Scripts/python.exe -m scripts.telegram_sim --text "Buy now, guaranteed 40% returns!"
```

This builds a realistic fake Telegram `Update` (the exact shape `getUpdates`
would return) and drives it through `app/channels/telegram.dispatch_update` —
the same function the real poller below calls. The verdict is always real
(ingest -> hash -> registry match -> claims/risk -> decide()), run against
the actual seeded registry; only the fact that it "arrived via Telegram" is
faked. Only the outbound send is logged instead of sent.

## Going live

Telegram is the one channel here that needs no public URL or tunnel at
all — `getUpdates` is pull-based (long-polling), so a bot token is the only
thing standing between this and working for real.

1. Message **@BotFather** on Telegram, send `/newbot`, follow the prompts.
   You'll get back a token like `123456789:AAH...`.
2. Add to `.env` (repo root):
   ```
   CHANNEL_TELEGRAM_ENABLED=true
   TELEGRAM_BOT_TOKEN=123456789:AAH...
   ```
3. Run the real poller (a separate long-lived process from the API server):
   ```
   cd backend
   .venv/Scripts/python.exe -m scripts.telegram_poll
   ```
4. Message your bot (search its @username in Telegram) with a photo, PDF,
   video, or plain text. It replies with the real verdict card and inline
   certificate/SEBI-check buttons.

## Gotchas

- **20 MB hard cap.** Telegram's Bot API refuses `getFile` for anything
  over 20 MB, independent of this project's own 64 MB video cap
  (`settings.max_video_bytes`) — that's a platform ceiling, not a bug here.
  The poller replies with a clear "too large for this bot to fetch" message
  instead of crashing.
- **If you ever set a webhook URL for this token** (e.g. testing something
  else), `getUpdates` will 409. `scripts/telegram_poll.py` calls
  `deleteWebhook` at startup to guard against this, so it's harmless, but
  worth knowing if you see a 409 anywhere else.
- The poller persists its `offset` (Telegram's ack mechanism) to Redis
  (`trustrail:telegram:offset`) so restarting it doesn't reprocess already-
  handled messages.
