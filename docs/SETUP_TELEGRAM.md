# Telegram channel

Telegram supports two transport modes, mutually exclusive at the API level
(a bot token can be polled via `getUpdates` OR have a webhook registered,
never both at once):

| | Polling (default) | Webhook |
|---|---|---|
| Direction | Your process pulls from Telegram | Telegram pushes to you |
| Needs a public URL? | No | Yes (tunnel or real deployment) |
| Entrypoint | `scripts/telegram_poll.py` | `POST /api/webhooks/telegram` |
| Simulator | `scripts/telegram_sim.py` (in-process, no server needed) | `scripts/telegram_webhook_sim.py` (real HTTP, needs the backend running) |

Both modes call the exact same [`dispatch_update()`](../backend/app/channels/telegram.py)
function, so the verdict can never drift between them — only the transport
differs. Polling is the simpler default for local dev (no tunnel needed);
the webhook exists for parity with how WhatsApp is built, and is what
you'd actually run in a real deployment (lower latency, no polling loop to
keep alive).

## Testing today (no bot token needed, no server needed)

```
cd backend
.venv/Scripts/python.exe -m scripts.telegram_sim --file ../fixtures/generated/filing_kumaon_q1.pdf
.venv/Scripts/python.exe -m scripts.telegram_sim --text "Buy now, guaranteed 40% returns!"
```

This builds a realistic fake `Update` (the exact shape `getUpdates` would
return) and drives it through `dispatch_update()` directly — no bot token,
no running server. The verdict is always real, run against the actual
seeded registry; only the fact that it "arrived via Telegram" is faked.

## Testing the webhook (no bot token needed, backend must be running)

```
cd backend
CHANNEL_TELEGRAM_ENABLED=true TELEGRAM_WEBHOOK_SECRET=sim_test_secret \
  .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

then in another terminal:

```
CHANNEL_TELEGRAM_ENABLED=true TELEGRAM_WEBHOOK_SECRET=sim_test_secret \
  .venv/Scripts/python.exe -m scripts.telegram_webhook_sim --file ../fixtures/generated/notice_meridian_margin.jpg
```

Like WhatsApp's signature check, `verify_webhook_secret()`
[**fails closed**](../backend/app/channels/telegram.py): with no
`TELEGRAM_WEBHOOK_SECRET` configured, every request is rejected outright,
so you need a matching value on both sides even for local sim testing (it
doesn't need to be a value Telegram itself knows about yet — that only
matters once you register a real webhook). This POSTs over real HTTP to
the running backend — the whole route runs for real, secret check
included. The webhook's own response only reports `{"handled": 1}` (Telegram
never reads the response body, so this mirrors the real contract); **the
composed reply is only visible in the backend's own log** — run uvicorn
with logging configured to see it:

```
.venv/Scripts/python.exe -c "import logging; logging.basicConfig(level=logging.INFO); import uvicorn; uvicorn.run('app.main:app', port=8000)"
```

## Going live — polling (simplest, no public URL needed)

1. Message **@BotFather** on Telegram, send `/newbot`, follow the prompts.
   You'll get back a token like `123456789:AAH...`.
2. Add to `.env`:
   ```
   CHANNEL_TELEGRAM_ENABLED=true
   TELEGRAM_BOT_TOKEN=123456789:AAH...
   ```
3. Run the poller (a separate long-lived process from the API server):
   ```
   cd backend
   .venv/Scripts/python.exe -m scripts.telegram_poll
   ```
4. Message your bot with a photo, PDF, video, or plain text. It replies
   with the real verdict card and inline certificate/SEBI-check buttons.

## Going live — webhook (needs a public URL, matches WhatsApp's model)

1. Steps 1-2 above (bot token from BotFather).
2. Pick a secret string and add it too: `TELEGRAM_WEBHOOK_SECRET=<any string you choose>`.
3. Start a tunnel, e.g. `ngrok http 8000` — copy the `https://...ngrok...` URL.
4. Register the webhook:
   ```
   cd backend
   .venv/Scripts/python.exe -m scripts.telegram_set_webhook https://your-tunnel.example/api/webhooks/telegram
   ```
5. Message your bot — Telegram now pushes updates to your webhook instead
   of you polling for them.
6. To switch back to polling later: `python -m scripts.telegram_delete_webhook`
   (or just start `scripts/telegram_poll.py`, which does this automatically
   at startup).

## Gotchas

- **20 MB hard cap.** Telegram's Bot API refuses `getFile` for anything
  over 20 MB, independent of this project's own 64 MB video cap
  (`settings.max_video_bytes`) — that's a platform ceiling, not a bug here.
  Both transports reply with a clear "too large for this bot to fetch"
  message instead of crashing.
- **Polling and webhook are mutually exclusive.** Registering a webhook
  makes `getUpdates` (what the poller uses) return 409 until the webhook is
  deleted. `scripts/telegram_poll.py` calls `delete_webhook()` itself at
  startup as a guard, but don't run the poller and a live webhook against
  the same bot token at the same time.
- The poller persists its `offset` (Telegram's ack mechanism) to Redis
  (`trustrail:telegram:offset`) so restarting it doesn't reprocess already-
  handled messages. The webhook has no equivalent ack state — a failure
  is logged and dropped (Telegram is told 200 regardless, to avoid a retry
  storm), same posture as the WhatsApp webhook.
