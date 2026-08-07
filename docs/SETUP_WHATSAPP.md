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
always — the verification pipeline. Test it right now with the backend
running (`CHANNEL_WHATSAPP_ENABLED=true` in `.env`, or set inline for a
one-off run):

```
cd backend
CHANNEL_WHATSAPP_ENABLED=true .venv/Scripts/python.exe -m scripts.whatsapp_sim --file ../assets_input/image1.jpg
.venv/Scripts/python.exe -m scripts.whatsapp_sim --text "Buy now, guaranteed returns!"
```

This builds a byte-accurate fake Cloud API webhook payload
(`entry[].changes[].value.messages[]`, Meta's real shape) and **really
POSTs it over HTTP** to your locally-running backend — it's not an
in-process shortcut, the whole route (including signature verification, if
`WHATSAPP_APP_SECRET` is set) runs for real. The verdict is genuine, run
against the real seeded registry. Only two things are faked, both clearly
marked:
- the media itself: since there's no live Graph API to resolve a fake
  `media_id`, the simulator attaches a `_sim_local_path` key (never present
  in a real Meta payload) that `channels/whatsapp.py` reads bytes from
  directly instead of calling the Graph API;
- the reply: instead of a real `POST` to the Graph API's `/messages`
  endpoint, the composed message is returned in the webhook's own HTTP
  response under `simulated_outbound` (Meta's real contract ignores the
  webhook's response body entirely, so this is purely additive and
  disappears automatically once real credentials are set).

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
   verdict.

## The one real fidelity gap: buttons

Meta's real interactive **session** messages support at most **one** URL
button (`interactive.type: "cta_url"`) — there's no native multi-URL-button
message type the way Telegram's `inline_keyboard` has. This project's
`render_verdict()` can produce up to 3 buttons (certificate, SEBI-check,
and a web-only "expand trace" accordion trigger with no chat equivalent).

**Resolution** (in `channels/whatsapp.py::_format_reply`): send one
`cta_url` message carrying the highest-priority link (the certificate if
present, otherwise SEBI-check) alongside the headline/body/top reason, then
a plain-text follow-up with any remaining reason strings and the other URL
as a bare `https://` string (WhatsApp auto-links these in body text — no
button chrome, but still tappable). This is a deliberate, documented
deviation from the original build spec's "interactive button message"
wording, not an oversight.
