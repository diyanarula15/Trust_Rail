# SMS channel + Trust Circle Auto-Guard

Two genuinely different integrations share this one channel adapter
([`channels/sms.py`](../backend/app/channels/sms.py)) — read this before
assuming either one, because they need different things to go live and
solve different problems.

| | Direct | Auto-Guard |
|---|---|---|
| What it is | A dedicated number people text the bot at, two-way, like WhatsApp/Telegram/email | Every message on **someone's own phone** scanned automatically, no forwarding |
| Needs a Twilio account? | Yes | No |
| Needs the person to do anything? | Yes — forward the suspicious text | No — that's the entire point |
| Entrypoint | `POST /api/webhooks/sms` | `POST /api/webhooks/sms/{guard_token}` |
| Auth | Twilio signature, always required | Twilio signature *or* the token itself (see below) |
| Enable from | `.env` (`CHANNEL_SMS_ENABLED=true`) | `/trust-circle/{token}` guardian dashboard — no `.env` change needed |

Both run through the identical `channels.sms.build_reply()` → the real
verification pipeline → `render.py`, exactly like every other channel in
this codebase — the only thing that differs is how a message reaches that
function and what happens with the answer.

## Direct: testing today (no Twilio account, no server needed)

```
cd backend
.venv/bin/python -m scripts.sms_sim --text "Buy now, guaranteed 40% returns!"
```

Drives `channels.sms.build_reply()` directly — no signature, no network
call, the exact function `/channels`'s web simulator also calls. The
verdict is always real, run against the actual seeded registry; only the
fact that it "arrived via SMS" is faked.

## Direct: testing the webhook (no Twilio account, backend must be running)

```
cd backend
CHANNEL_SMS_ENABLED=true TWILIO_AUTH_TOKEN=sim_test_token \
  .venv/bin/uvicorn app.main:app --port 8000
```

then in another terminal:

```
cd backend
CHANNEL_SMS_ENABLED=true TWILIO_AUTH_TOKEN=sim_test_token \
  .venv/bin/python -m scripts.sms_webhook_sim --text "Pay now via UPI scam@okpay"
```

Like WhatsApp's and Telegram's signature checks,
[`verify_twilio_signature()`](../backend/app/channels/sms.py) **fails
closed**: with no `TWILIO_AUTH_TOKEN` configured, every request is
rejected outright, so both sides need a matching value even for local sim
testing (it doesn't need to be your real Twilio auth token — that only
matters once you're actually pointing a real number here). This POSTs
over real HTTP with a genuine, correctly-computed Twilio-style signature —
the whole route runs for real, signature check included.

## Direct: going live

1. Buy a number in the [Twilio console](https://console.twilio.com) (trial
   accounts get one free).
2. Add to `.env`:
   ```
   CHANNEL_SMS_ENABLED=true
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your_real_auth_token
   TWILIO_FROM_NUMBER=+1xxxxxxxxxx
   ```
3. Start a tunnel, e.g. `ngrok http 8000`.
4. In the Twilio console, under your number's **Messaging** configuration,
   set "A message comes in" to a webhook: `https://your-tunnel.example/api/webhooks/sms`.
5. Text the number. It replies with the real verdict.

## Auto-Guard: what it actually is

The direct path above still asks something of the person being protected —
forward the message, wait for a reply. Auto-Guard removes that step
entirely: a family member enables it from the elder's `/trust-circle/{token}`
dashboard, gets back a private webhook address
(`{api_base_url}/api/webhooks/sms/{guard_token}`), and configures **something
on the elder's own phone** to POST every incoming SMS to that address the
instant it arrives. From then on, nothing is forwarded by hand and nothing
is left to notice — the guardian is alerted directly if something dangerous
gets through.

Two real ways to wire that phone-side piece up, and the webhook accepts
either without needing to know which one you used:

- **An SMS-forwarder app** (search "SMS Forwarder" or "SMS Gateway" on the
  Play Store) installed on the elder's own phone. This is the actual point
  of the feature: their existing number, unmodified, silently mirrored.
  These apps typically POST a small JSON body; the webhook reads `from`/
  `body` (or `sender`/`text`/`message` — field names vary between apps) and
  doesn't require a Twilio signature, since a phone-side forwarder app has
  no way to produce one. Whoever holds the `guard_token` URL *is* the
  authentication — the same bearer-capability pattern `circle_token` and
  certificate links already use elsewhere in this app.
- **A dedicated Twilio number**, exactly like the Direct integration above,
  except its webhook points at the guard-token URL instead of the plain one.
  Real: works for a business number that's meant to be monitored rather
  than an elder's own personal line. When Twilio calls this route, its
  signature *is* checked (and must be valid if present) — the difference
  from the Direct route is only that an unsigned request isn't rejected
  outright, since Auto-Guard's other real integration path has no signature
  at all.

## Auto-Guard: seeing it work right now (no phone, no Twilio account)

The guardian dashboard at `/trust-circle/{token}` has a "send a test
message" panel once Auto-Guard is enabled — it posts a real message to the
real webhook URL and the resulting alert (if any) shows up in "Recent
alerts" a moment later. That's not a simulator response; it's the same
route a real phone would call.

The equivalent from a terminal, exercising the identical DB-backed flow end
to end (pairing, enabling, a scam text landing an alert, a benign one
correctly not, disabling revoking the old URL):

```
cd backend
.venv/bin/python -m scripts.smoke_circle
```

## Gotchas

- **`is_live()` gates the outbound send only**, not the webhook routes
  themselves. `CHANNEL_SMS_ENABLED` and `trust_circle_enabled` (on by
  default) independently control whether each *route* is reachable at all;
  `TWILIO_ACCOUNT_SID`/`TWILIO_FROM_NUMBER` being unset just means replies
  are logged instead of actually sent over Twilio's API — this matters for
  Auto-Guard especially, since it never sends a reply at all (see
  `channels/sms.handle_guard_inbound`'s docstring for why replying to the
  original sender would be actively wrong).
- **Auto-Guard doesn't reply to the original sender, ever, on purpose.**
  The `From` field in a forwarded payload is whoever texted the elder — a
  scammer, most of the time — not the elder. Replying there would help no
  one and could tip off whoever sent it.
- **No `/circle` command handling inside Auto-Guard's inbound stream.**
  That stream is every message *someone else* sent *to* the elder's phone;
  there's no scenario where a guardian would text the elder's own number to
  link their own alert channel. Guardians link their channel from wherever
  they're actually talking to the bot — see the main
  [Trust Circle pairing flow](../backend/app/circle/pairing.py).
- **Twilio's signature covers the exact request URL**, including scheme —
  behind a reverse proxy that terminates TLS before FastAPI sees the
  request, `request.url` may report `http://` when Twilio signed
  `https://`, and the signature will (correctly) fail to verify. Not an
  issue for `ngrok`/direct deployment; worth knowing if you put anything in
  front of this.
