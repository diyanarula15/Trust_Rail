# WhatsApp channel

**Ships simulated today, and will keep shipping simulated until a Meta
Business account is available.** Unlike Telegram/email, this isn't a "we
haven't gotten around to it yet" gap — WhatsApp's Cloud API has **no
polling mode**. Meta only ever pushes messages to a webhook you register,
so this channel cannot go live without both a Meta developer app *and* a
public HTTPS URL (a tunnel like ngrok/cloudflared, or a real deployment).
Neither exists for this project yet.

What *is* real: the webhook contract itself
(`GET`/`POST /api/webhooks/whatsapp` in `backend/app/api/webhooks_whatsapp.py`),
signature verification, the two-step media-download shape, and — as
always — the verification pipeline (`_handle_one` in
`webhooks_whatsapp.py` drains the exact same `_run_verification` generator
`POST /api/verify` uses). Test it right now with the backend running:

```
cd backend
CHANNEL_WHATSAPP_ENABLED=true WHATSAPP_APP_SECRET=sim_test_secret \
  .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

then in another terminal:

```
CHANNEL_WHATSAPP_ENABLED=true WHATSAPP_APP_SECRET=sim_test_secret \
  .venv/Scripts/python.exe -m scripts.whatsapp_sim --file ../fixtures/generated/notice_meridian_margin.jpg
.venv/Scripts/python.exe -m scripts.whatsapp_sim --text "Buy now, guaranteed returns!"
```

`WHATSAPP_APP_SECRET` doesn't need to be a real Meta value here — the
webhook's signature check (`channels/whatsapp.verify_webhook_signature`)
**fails closed**: with no secret configured it rejects every request
outright (deliberately — an unsigned webhook accepting fabricated
verification traffic would be a bad look for a system whose entire product
is authenticity). Setting any matching value on both the server and
`whatsapp_sim.py` is enough to exercise the real HMAC check end to end
locally.

This builds a realistic fake Cloud API webhook payload
(`entry[].changes[].value.messages[]`, Meta's real shape) and **really
POSTs it over HTTP** to your locally-running backend — the whole route
runs for real, signature check included. The verdict is genuine, run
against the real seeded registry. Only two things are faked, both clearly
marked in the code:
- the media itself: since there's no live Graph API to resolve a fake
  `media_id`, the simulator attaches a `_sim_local_path` key (never present
  in a real Meta payload) that `channels/whatsapp.download_media` reads
  bytes from directly instead of calling the Graph API;
- the reply: `channels/whatsapp.send_text` calls the real Graph API only
  when `enabled()` is true (`CHANNEL_WHATSAPP_ENABLED` + a real
  `WHATSAPP_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID`); otherwise it logs the
  composed message instead of sending it. The webhook's HTTP response
  itself just reports `{"handled": N}` (matching Meta's real contract,
  which never inspects the response body) — **the composed reply is only
  visible in the backend's own log**, e.g. run uvicorn with logging
  configured (`python -c "import logging;
  logging.basicConfig(level=logging.INFO); import uvicorn;
  uvicorn.run('app.main:app', port=8000)"`) to see it printed as
  `app.channels.whatsapp INFO: whatsapp disabled; reply for ...`.

## Going live (when a Meta Business account exists)

1. Create a Meta developer app at developers.facebook.com, add the
   **WhatsApp** product. It comes with a free test number and a temporary
   24-hour access token to start with (a permanent token needs a verified
   Business Manager account).
2. Start a tunnel so Meta can reach your local machine, e.g.
   `ngrok http 8000` — copy the `https://...ngrok...` URL it gives you.
3. In the Meta app's WhatsApp > Configuration page, set the webhook
   callback URL to `https://<your-tunnel>/api/webhooks/whatsapp` and the
   verify token to whatever you put in `.env`'s `WHATSAPP_VERIFY_TOKEN`
   (any string you choose — Meta echoes it back on the `GET` handshake).
4. Add to `.env`:
   ```
   CHANNEL_WHATSAPP_ENABLED=true
   WHATSAPP_TOKEN=<access token from the Meta app>
   WHATSAPP_PHONE_NUMBER_ID=<from the Meta app's API setup page>
   WHATSAPP_VERIFY_TOKEN=<any string you chose in step 3>
   WHATSAPP_APP_SECRET=<from the Meta app's Basic Settings, enables real signature checks>
   ```
5. Message the test number from WhatsApp. It should reply with the real
   verdict as plain WhatsApp text (`channels/whatsapp.format_card`).

## Design notes

- The webhook always returns `200` to Meta, even on internal failure —
  Meta retries non-200 responses aggressively, and a retry storm on a
  failing message helps nobody. Problems are logged server-side instead
  (see `api/webhooks_whatsapp.py`'s module docstring).
- Replies are plain WhatsApp text, not interactive button messages —
  `format_card()` renders the certificate link as a plain
  `label: https://...` line (WhatsApp auto-links bare URLs in body text)
  rather than a native button. Simpler than the interactive `cta_url`
  message type, and avoids Meta's real limit of one URL button per
  session message, which doesn't map cleanly onto this project's up-to-2
  URL buttons (certificate + SEBI-check).
