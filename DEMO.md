# TrustRail Demo Runbook

Follow this exactly. Every step names the real button, the real file, and
the real verdict you should see. Nothing here requires reading code.

## 0. Reset

This machine has no `make` binary (Windows, no Chocolatey/WSL `make`
installed), so run the three commands `make demo-reset` would chain, from
`backend/`:

```
.venv\Scripts\python.exe -m alembic downgrade base
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m scripts.seed
```

(On a machine with `make` installed, just run `make demo-reset`.)

This wipes and rebuilds the whole demo world: 12 entities, 15 signing
keys, the `FXROAD-DEMO` blacklist fixtures, 10 pre-published communications
(3 filings, 3 images, 3 SMS, 1 email), and 60 days of historical telemetry.
It prints a cheat sheet at the end with entity IDs and the file list.

Then start both servers (each in its own terminal, from the repo root):

```
cd backend  &&  .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
cd frontend &&  pnpm dev
```

Open three browser tabs: **http://localhost:3000/issuer**, **/verify**, and
**/supervision**.

## 1. Issuer: publish the CEO announcement live

In the **/issuer** tab:
1. Entity dropdown → **Kumaon Metals Ltd**.
2. Persona dropdown → the entry ending in **(maker, active)**.
3. Click **New communication**. Title: `Kumaon Metals CEO announcement`.
   Channel: `video`. Impact: `market_moving`. File: `assets_input/ceo_announcement.mp4`.
   Click **Create draft**.
4. On the new row, click **Sign (maker)**.
5. Switch the persona dropdown to the entry ending in **(checker, active)**.
6. Click **Co-sign & publish** on the same row.
7. Point at the green banner: **"Log root updated: `<old>` → `<new>`"**.
   That's the transparency log advancing live, on this exact click.

*(The video isn't pre-published by the seed script on purpose. This step
is the first time it's ever published, so the root-delta banner means
something.)*

## 2. Terminal: mangle the video like WhatsApp would

```
cd backend
.venv\Scripts\python.exe -m scripts.wa_sim_transform ..\assets_input\ceo_announcement.mp4 --preset crf26 -o ..\assets_input\ceo_mangled.mp4
```

This re-encodes at 848px width and CRF 26, and strips metadata: the same
`ffmpeg` flags a real WhatsApp forward applies.

## 3. Verify: the mangled video still checks out

In the **/verify** tab: drop `assets_input/ceo_mangled.mp4` into the
composer, leave everything else blank, click **Send**.

Expect: **✅ Verified**, entity Kumaon Metals Ltd, log entry matching what
you just published in step 1. Click **"How this was checked"**: the trace
reads `hard_binding: no manifest` → `registry_match: video match` (the
re-encode destroyed any embedded manifest, so the video frame hash match is
what actually verified it; this is the whole reason soft binding exists).

Below the trace, the **evidence panel** shows the working rather than
asking anyone to take it on faith: the frame strip marks which sampled
frames matched and how many were needed. **This is the panel to linger on.**
It is at its most convincing on an image (step 3b below), where the two
SHA-256s are visibly, completely different while the two perceptual
fingerprints are identical or near-identical. That contrast *is* the
argument for why soft binding has to exist.

### 3b. The same thing, but on an image (the clearest version)

In a terminal, mangle a registered image and submit it:

```
cd backend
.venv/bin/python -m scripts.wa_sim_transform ../assets_input/image1.jpg --preset screenshot_sim -o ../assets_input/image1_shot.jpg
```

Drop `image1_shot.jpg` into **/verify** and open **"How this was checked"**.
Expect ✅ Verified (Meridian Broking Ltd) and, in the panel:

- the image you sent beside the one Meridian published;
- **Byte hash (SHA-256): completely different** — a 2.5% crop rewrote every byte;
- **Perceptual fingerprint: 10 of 64 bits differ**, drawn as two 8x8 grids
  with the ten differing cells ringed. Those grids are not a diagram of the
  hash: a phash64 *is* an 8x8 grid of bits, so you are looking at the hash
  itself;
- the distance scale showing 10 sitting right on the match line.

Then submit any unrelated photo. Same panel, honest opposite result:
"closest registered item was ~32 of 64 bits away, well past the 10-bit
match line," and the verdict stays a calm ℹ️ Informational rather than an
accusation.
Click **View certificate** to open the one-time certificate page. Note it
shows the signature chain and log root; if you reload that same link it
will now show a "used" state (single use, as designed).

## 4. Verify: a tampered filing

In **/verify**, use **Drop a file** and pick `assets_input/filing1.pdf`
with "Claimed sender" set to `Kumaon Metals Ltd`. Send it as-is once to
see it hash match (✅ Verified). Then open the PDF, change the "Revenue
from operations" figure (`9,588.18` → anything else), save it, and submit
the modified copy with the same claimed sender.

Expect **🚨 High risk — likely fake** (`LIKELY_FAKE`), with
`TAMPERED_CONTENT` among the reasons and the card's "Why this answer"
explaining that the wording matches a published filing but the figures do
not.

This is worth narrating carefully, because it is the strongest thing in
the demo. The file differs from the published one, but so does any
re-saved copy — that alone proves nothing. What convicts it is that the
*wording* still matches a real Kumaon Metals filing while the *numbers*
do not. Forwarding never edits numbers; altering a figure is precisely an
edit of numbers.

A ready-made doctored copy ships as
`fixtures/generated/filing_kumaon_q1_TAMPERED.pdf` if you would rather not
edit a PDF live.

*(Prior builds returned "cannot be confirmed" here, and earlier still this
case passed as ✅ Verified — a doctored figure moves the text fingerprint
by only 2 bits against a threshold of 6. `scripts/acceptance.py` caught
that; the numeric guard fixes it. See PROGRESS.md.)*

## 5. Verify: the fake IPO SMS

In **/verify**, switch to **Paste text**, paste exactly:

```
MERIDN IPO allotment confirmed! Pay allotment fee now to http://rneridianbroking-refunds.top/claim. Last 2 hours only. Pay via UPI meridianrefund@okpay
```

Expect: **🚨 High risk — likely fake**, reasons include `LOOKALIKE_DOMAIN`
and `BLACKLIST_MATCH`, and the card names the campaign **FXROAD-DEMO**.

## 6. Verify: a plain news paragraph

Paste: `Benchmark indices ended higher today led by banking and IT stocks.`

Expect: **ℹ️ No official claim detected**, calm rather than alarming. This
is the base-rate answer: most forwarded content makes no claim at all, and
the system says so plainly instead of guessing.

## 7. Supervision: see the flags land

Switch to the **/supervision** tab (polls every 10s, so wait a moment
after step 5). The India map should show a flagged count on whichever
state you picked in step 5's `state_code` field (add one if you skipped
it), and the campaigns table should show **FXROAD-DEMO**.

## 8. Admin: revoke the key, re-verify

Back in **/issuer**, with **Kumaon Metals Ltd** and the **maker** persona
selected, click **Simulate key compromise**. Read the banner. Now go back
to **/verify** and re-submit the *same mangled video* from step 3.

Expect: **⚠️ Verified — with notice** (`KEY_REVOKED_AFTER_SIGNING`) instead
of a plain Verified. The content still matches, but the signing key is now
known compromised. Open **/log** and confirm the revocation is its own log
entry (not a silent edit) and that the original publish entry (step 1)
still verifies its inclusion proof.

---

**Contingency:** if anything breaks live, re-run step 0. It restores a
clean world in under a minute. Keep a screen recording of a full pass as
backup.
