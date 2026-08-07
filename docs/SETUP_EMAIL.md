# Email channel

**Ships simulated today.** No mailbox is configured, so nothing polls a
real inbox. Test it right now with:

```
cd backend
.venv/Scripts/python.exe -m scripts.email_sim
```

With no `--file`, this cycles through the two real fixtures already in the
repo (`fixtures/eml_samples/forwarded_legit.eml` and
`fixtures/eml_samples/lookalike_scam.eml`) and drives each through
`app/channels/email_channel.handle_raw_message` — the same function the real
poller below calls. The verdict is always real, including the genuine
DKIM/domain-lookalike checks in `pipeline/emailcheck.py` (you should see the
two fixtures produce meaningfully different verdicts); only the mailbox
transport (IMAP fetch, SMTP send) is faked — the composed reply is printed
instead of sent.

```
.venv/Scripts/python.exe -m scripts.email_sim --file path\to\any.eml
```

## Going live

Like Telegram, this uses polling (IMAP `SEARCH UNSEEN`), so no public URL
or DNS/MX/inbound-parse setup is needed — just a mailbox.

1. Get an inbox you're willing to dedicate to this. For Gmail: enable
   2-Step Verification, then create an **App Password**
   (Google Account -> Security -> App passwords) — don't use your normal
   password, Gmail blocks plain IMAP logins with it.
2. Add to `.env` (repo root):
   ```
   CHANNEL_EMAIL_ENABLED=true
   EMAIL_IMAP_HOST=imap.gmail.com
   EMAIL_IMAP_PORT=993
   EMAIL_SMTP_HOST=smtp.gmail.com
   EMAIL_SMTP_PORT=587
   EMAIL_USERNAME=your-bot-inbox@gmail.com
   EMAIL_PASSWORD=<the 16-char app password>
   ```
3. Run the real poller (a separate long-lived process from the API server):
   ```
   cd backend
   .venv/Scripts/python.exe -m scripts.email_poll
   ```
4. Forward (or attach) a suspicious email to that inbox. Within
   `EMAIL_POLL_INTERVAL_SECONDS` (default 30s) you'll get a reply with the
   real verdict, threaded under the original message.

## Gotchas / design notes

- **Loop-prevention is the biggest real risk with a live inbox.** The
  poller never replies to: its own address, anything with an
  `Auto-Submitted` header that isn't `no` (RFC 3834 — out-of-office and
  other auto-responders), or anything that looks like a bounce/DSN
  (`multipart/report`, `mailer-daemon@`/`postmaster@`). If you ever see
  unexpected reply traffic, this is the first place to check.
- **Only the outer message is verified**, not a nested `message/rfc822`
  *attachment*. If your mail client attaches the original scam email as a
  file rather than doing an inline "Forward", verify that attachment
  directly instead (or via the web `/verify` simulator's file upload).
- Fetches use `BODY.PEEK[]` and only mark a message `\Seen` in a `finally`
  after attempting to handle it — this is the ack mechanism (mirrors
  Telegram's offset-advance): a crash mid-handling can't lose the message,
  and a permanently-bad message can't wedge the poller either.
- A forwarded email genuinely lacks the original sender's
  `Authentication-Results`/DKIM headers — `pipeline/emailcheck.py` already
  reports this honestly as `AUTH_HEADERS_UNAVAILABLE` rather than treating
  the absence as a pass. That's expected on most real forwards, not a bug.
