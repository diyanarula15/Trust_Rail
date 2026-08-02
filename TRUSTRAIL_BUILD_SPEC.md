# TRUSTRAIL: BUILD SPECIFICATION v1.0
## Owner: Manan | Target: SEBI Securities Market TechSprint 2026, Problem Statement 1

This spec describes **TrustRail**, a working prototype of a content-authenticity rail for India's securities market. Investors forward suspicious content (video, image, PDF, SMS text, email, URL); TrustRail answers whether a SEBI-registered entity actually issued it: using cryptographic provenance first and risk heuristics last.

Read this ENTIRE file before writing any code. Then execute epic-by-epic (Section 17), stopping at each epic gate for the owner's go-ahead. Maintain PROGRESS.md at repo root after every epic.

---

## 1. MISSION & DEMO OUTCOME

The prototype must support this exact 5-minute demo without failure:

1. Issuer console: a mock listed company drafts a "CEO announcement" video + a PDF filing → maker signs → checker co-signs → published. Artifact hashes + signature envelope land in a tamper-evident transparency log. Live UI shows the log root updating.
2. Verify surface (WhatsApp-style simulator): forward the SAME video after it has been "WhatsApp-mangled" (re-encoded, metadata stripped, by our transform script) → verdict: **✅ Verified**, with issuer, timestamp, log entry #, and a working one-time certificate link showing a Merkle inclusion proof verifying live.
3. Forward a tampered/fake version claiming to be from the same company → **🚨 High risk**, with human-readable reasons (claims registered entity + no registry match + lookalike domain).
4. Forward a random news paragraph → **ℹ️ Informational: no official claim detected** (this proves the base-rate problem is solved; it must NOT say "unverifiable" in an alarming way).
5. Supervision dashboard: the two bad forwards appear as telemetry pins on an India map with campaign clustering.
6. Admin: revoke the company's signing key → re-verify item (1) → verdict becomes **⚠️ Verified with notice** (key later revoked, content signed while valid). Log remains intact and provable.

Everything else in this spec exists to make those six moments real, fast, and honest.

---

## 2. NON-NEGOTIABLE ENGINEERING PRINCIPLES

1. **Never fake cryptography.** "Verified" is emitted ONLY when a signature chain validates to the demo trust root OR content hash-matches a published registry artifact. No shortcuts, no hardcoded verdicts.
2. **Never fake ML confidence.** We do not ship a deepfake classifier in this build. When provenance is absent, say so honestly with reason codes. No invented percentages anywhere in the UI.
3. **Honest vocabulary.** UI copy says "digital signature", "tamper-evident log", "maker-checker". NEVER: "blockchain", "crypto", "ledger", "token" (except "view token" internally), "multi-sig".
4. **Fictional fixtures only.** Demo entities are invented ("Meridian Broking Ltd"), never real brands. No deepfakes of real people anywhere in the repo: the demo "CEO video" is footage the owner supplies of himself.
5. **Fail loud in dev, degrade gracefully in demo.** Optional dependencies (c2pa, pdqhash, Anthropic API) wrap in try/except with feature flags; the core path must work with zero optional deps.
6. **Every verdict carries reasons.** The API never returns a bare verdict; it returns machine reason codes + localized human advice.
7. **Small, typed, tested.** Python fully type-hinted, Pydantic v2 models at all boundaries, pytest for trust core + verdict engine. Target ≤ ~6k LOC backend. TODO(prod) comments welcome; dead code is not.
8. **Commit per epic** with message `Epic N: <summary>`. Never commit `var/`, `.env`, or `assets_input/` media.

---

## 3. LOCKED TECH STACK

Backend:
- Python 3.11+, FastAPI, Uvicorn
- SQLAlchemy 2.x + Alembic, psycopg[binary], PostgreSQL 16
- Pydantic v2 + pydantic-settings
- Redis 7 (rate limiting; job queue only if WhatsApp channel enabled)
- Crypto: PyNaCl (Ed25519), cryptography (X.509 chain, P-256 for C2PA cert)
- Media: Pillow, imagehash (REQUIRED); pdqhash (OPTIONAL, try/except); ffmpeg via subprocess (system binary)
- c2pa-python (OPTIONAL embed/read; envelope path is the required baseline)
- Text/claims: rapidfuzz, confusable-homoglyphs
- Email/DNS: stdlib email parser, dnspython
- httpx, python-multipart, python-magic

Frontend:
- Next.js 14 (App Router) + TypeScript, Tailwind CSS, shadcn/ui
- recharts (charts), react-simple-maps + India TopoJSON (checked into repo)
- lucide-react icons, zustand for light state

Infra:
- docker-compose: postgres:16-alpine, redis:7-alpine (app runs on host for dev speed)
- Makefile as the single entry point for every workflow

Optional integrations (feature-flagged, default OFF):
- WhatsApp Business Cloud API adapter
- Anthropic API for claim extraction (rule-based extractor is the required baseline)

---

## 4. REPOSITORY LAYOUT

```
trustrail/
├── TRUSTRAIL_BUILD_SPEC.md        # this file
├── PROGRESS.md                    # you maintain this
├── README.md                      # quickstart + screenshots
├── DEMO.md                        # exact demo runbook (Section 18)
├── Makefile
├── docker-compose.yml
├── .env.example
├── .gitignore                     # var/, .env, assets_input/*, node_modules, __pycache__
├── docs/
│   ├── ARCHITECTURE.md            # diagrams + data flow
│   └── METRICS.md                 # generated by eval harness
├── assets_input/                  # OWNER-PROVIDED media (gitignored)
├── var/                           # runtime: artifacts/, trust/ (gitignored)
├── backend/
│   ├── requirements.txt
│   ├── alembic/ ...
│   ├── app/
│   │   ├── main.py                # FastAPI app factory, CORS, routers
│   │   ├── config.py              # pydantic-settings; ALL thresholds live here
│   │   ├── db.py                  # engine, session
│   │   ├── models.py              # SQLAlchemy models (Section 6)
│   │   ├── schemas.py             # Pydantic I/O models
│   │   ├── trust/
│   │   │   ├── ca.py              # demo root CA + entity cert issuance
│   │   │   ├── envelope.py        # TrustRail Signature Envelope v1 sign/verify
│   │   │   ├── merkle.py          # RFC6962-style log, proofs, signed tree heads
│   │   │   ├── revocation.py      # key + communication revocation logic
│   │   │   └── c2pa_embed.py      # optional C2PA embed/read wrapper
│   │   ├── pipeline/
│   │   │   ├── ingest.py          # type sniffing, size caps, normalization
│   │   │   ├── hashing.py         # sha256, phash64, optional pdq, video frame hashes
│   │   │   ├── media.py           # ffmpeg keyframe extraction
│   │   │   ├── claims.py          # entity-claim extraction (rule-based + optional LLM)
│   │   │   ├── risk.py            # phrase/URL/domain risk signals
│   │   │   ├── emailcheck.py      # .eml parsing, auth-results, domain alignment
│   │   │   └── verdict.py         # THE verdict engine (Section 8)
│   │   ├── api/
│   │   │   ├── verify.py          # POST /api/verify, GET /api/verifications/{id}
│   │   │   ├── issuer.py          # draft/sign/cosign/publish/revoke
│   │   │   ├── registry.py        # entities, domains, headers
│   │   │   ├── log.py             # roots, entries, inclusion proofs
│   │   │   ├── telemetry.py       # weather-map aggregates
│   │   │   ├── tokens.py          # one-time certificate view tokens
│   │   │   └── webhooks_whatsapp.py  # flag-gated
│   │   ├── channels/
│   │   │   ├── render.py          # verdict -> localized card payloads
│   │   │   └── whatsapp.py        # Cloud API client (flag-gated)
│   │   └── i18n/
│   │       ├── en.json
│   │       └── hi.json
│   ├── scripts/
│   │   ├── seed.py                # full demo world (Section 15)
│   │   ├── wa_sim_transform.py    # WhatsApp-mangle transforms (Section 16)
│   │   ├── evaluate.py            # metrics harness -> docs/METRICS.md
│   │   └── smoke.py               # end-to-end smoke: seed → publish → verify
│   └── tests/
│       ├── test_merkle.py
│       ├── test_envelope.py
│       ├── test_hash_matching.py
│       ├── test_claims.py
│       └── test_verdict.py
└── frontend/
    ├── package.json, tailwind.config.ts, etc.
    └── src/
        ├── app/
        │   ├── page.tsx           # landing: what TrustRail is + live stats strip
        │   ├── verify/page.tsx    # chat-style verify simulator
        │   ├── issuer/page.tsx    # issuer console (maker-checker)
        │   ├── registry/page.tsx  # entity explorer
        │   ├── log/page.tsx       # transparency log explorer + proof checker
        │   ├── supervision/page.tsx # SEBI weather map dashboard
        │   └── c/[token]/page.tsx # one-time certificate page
        ├── components/            # VerdictCard, PipelineTrace, MerkleProof, IndiaMap, ...
        ├── lib/api.ts             # typed client
        └── i18n/                  # en/hi dictionaries shared with card copy
```

---

## 5. ENVIRONMENT, COMPOSE, MAKEFILE

### 5.1 `.env.example`
```
DATABASE_URL=postgresql+psycopg://trustrail:trustrail@localhost:5433/trustrail
REDIS_URL=redis://localhost:6380/0
SECRET_KEY=change-me
BASE_URL=http://localhost:3000
API_BASE_URL=http://localhost:8000
ARTIFACT_DIR=./var/artifacts
TRUST_DIR=./var/trust
CERT_LINK_TTL_MINUTES=15
DEFAULT_LOCALE=en
SEBI_CHECK_URL=#            # TODO(owner): set official SEBI Check URL before demo
LLM_ENABLED=false
ANTHROPIC_API_KEY=
CHANNEL_WHATSAPP_ENABLED=false
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_APP_SECRET=
```

### 5.2 `docker-compose.yml`
Postgres 16 on host port **5433**, Redis 7 on host port **6380** (non-default ports to avoid collisions with the owner's other projects). Named volumes. Healthchecks on both.

### 5.3 `Makefile` targets (all must work)
```
make up          # docker compose up -d (db, redis) + wait for health
make install     # python venv + pip install -r backend/requirements.txt; pnpm install in frontend/
make migrate     # alembic upgrade head
make seed        # python -m scripts.seed  (idempotent: wipes + rebuilds demo world)
make api         # uvicorn app.main:app --reload --port 8000 (cwd backend/)
make web         # pnpm dev in frontend/ (port 3000)
make check       # pytest -q backend/tests && python -m scripts.smoke
make eval        # python -m scripts.evaluate  -> writes docs/METRICS.md
make demo-reset  # drop schema, migrate, seed, print demo checklist
```

---

## 6. DATA MODEL (SQLAlchemy models: Alembic migration 001)

All tables get `id` (UUID pk, default gen), `created_at` (tz-aware). Types below are the important columns.

**entities**: name (unique), kind enum(`regulator|exchange|listed_company|broker|mutual_fund|ria`), sebi_reg_no (string, clearly-demo format), status enum(`active|suspended`).

**entity_domains**: entity_id FK, domain (lowercase, unique), kind enum(`web|email`).

**entity_sms_headers**: entity_id FK, header (uppercase, unique, 6 chars).

**keys**: entity_id FK, label, role enum(`maker|checker|entity|registry`), public_key_ed25519 (b64), private_key_ed25519 (b64: DEMO ONLY, comment loudly; TODO(prod): HSM), cert_pem (nullable, P-256 leaf for C2PA), status enum(`active|revoked`), valid_from, revoked_at (nullable), revocation_reason.

**communications**: entity_id FK, title, channel enum(`filing|sms|email|video|image|pdf|social`), impact enum(`standard|market_moving`), status enum(`draft|maker_signed|published|revoked`), canonical_text (nullable: for text-born comms), artifact_id FK nullable, maker_key_id FK, maker_sig (b64, nullable), checker_key_id FK nullable, checker_sig nullable, published_at nullable, log_seq (nullable int).

**artifacts**: sha256 (hex, indexed), mime, bytes_size, storage_path (under ARTIFACT_DIR), phash64 (hex nullable, indexed), pdq256 (hex nullable), video_frame_hashes (JSONB: list of phash hex, nullable), simhash64 (hex nullable, for text/pdf-extracted), c2pa_embedded (bool), envelope (JSONB: full TrustRail envelope).

**log_entries**: seq (int, unique, monotonically increasing), leaf_hash (hex), entry (JSONB: {communication_id, artifact_sha256, entity_id, published_at, envelope_digest}), tree_size (int), root_hash (hex), sth_sig (b64: registry key over canonical STH), created_at.

**verifications**: channel enum(`sim|whatsapp`), input_kind enum(`image|video|pdf|text|url|eml`), verdict enum(`VERIFIED|VERIFIED_NOTICE|OFFICIAL_CLAIM_UNVERIFIED|LIKELY_FAKE|INFORMATIONAL`), reasons (JSONB array of codes), signals (JSONB: full pipeline trace), matched_entity_id nullable FK, matched_communication_id nullable FK, claimed_entity_text nullable, campaign nullable, state_code nullable (IN-state ISO like `IN-KA`), latency_ms int.

**scam_blacklist**: kind enum(`domain|phash|phrase`), value (text; phash as hex), campaign (string label), source (string), active bool.

**view_tokens**: token (unique, urlsafe), verification_id FK nullable, communication_id FK nullable, expires_at, used_at nullable.

Indexes: artifacts.sha256, artifacts.phash64, verifications.created_at, log_entries.seq.

---

## 7. TRUST & CRYPTO DESIGN

### 7.1 Demo certificate authority (`trust/ca.py`)
- On first `make seed`: generate **TrustRail Demo Root** (Ed25519 for envelopes; additionally a P-256 self-signed root cert if c2pa available), a **registry STH keypair** (Ed25519), and per-entity keypairs. Persist under `TRUST_DIR` as PEM/JSON; load lazily elsewhere.
- Featured entities (the 3 used in the demo) get separate **maker** and **checker** keypairs. Others get a single `entity` key.
- If `c2pa-python` importable: also issue per-entity P-256 leaf certs chained to the P-256 root, EKU includes emailProtection + clientAuth (c2pa signing requirement). Wrap all c2pa cert work in try/except; absence must not break anything.

### 7.2 TrustRail Signature Envelope v1 (`trust/envelope.py`): REQUIRED baseline
Canonical JSON (sorted keys, `separators=(",", ":")`, UTF-8):
```json
{
  "v": 1,
  "artifact_sha256": "<hex>",
  "entity_id": "<uuid>",
  "sebi_reg_no": "DEMO-INZ-000123",
  "communication_id": "<uuid>",
  "channel": "pdf",
  "impact": "market_moving",
  "issued_at": "2026-07-10T09:30:00+05:30",
  "maker": {"key_id": "<uuid>", "sig": "<b64>"},
  "checker": {"key_id": "<uuid>", "sig": "<b64>"}
}
```
- **Signing bytes** = SHA-256 of canonical JSON with BOTH `maker.sig` and `checker.sig` set to `""`. Maker and checker each Ed25519-sign those same bytes (checker sig required only when impact = market_moving).
- `verify_envelope(env) -> EnvelopeResult`: recompute signing bytes; verify sigs against the DB public keys; check entity status; return structured result {valid, maker_ok, checker_ok, key_states, signed_at}: never raise on bad input.

### 7.3 Transparency log (`trust/merkle.py`): RFC 6962 style
- `leaf_hash = SHA256(0x00 || canonical_json(entry))`; `node = SHA256(0x01 || left || right)`.
- Append-only: on publish, insert log_entries row with new tree_size, recomputed root, and STH signature = Ed25519(registry_key, canonical {tree_size, root_hash, timestamp}).
- `inclusion_proof(seq) -> {leaf_hash, audit_path: [hex...], tree_size, root_hash}` and a pure-function `verify_inclusion(leaf, path, size, root) -> bool` (mirror this exact function in TypeScript for the log explorer's client-side check).
- Tree is small (demo scale); recomputing from DB rows on each append is acceptable: keep it simple and correct. Cache latest root in Redis, invalidate on append.

### 7.4 Revocation (`trust/revocation.py`)
- Key revocation: sets status=revoked + revoked_at. Verdict rule: envelope valid AND signed_at < revoked_at → VERIFIED_NOTICE; signed_at ≥ revoked_at → signature treated as invalid (TAMPERED_SIGNATURE path).
- Communication revocation (withdrawal): status=revoked; registry matches to it yield OFFICIAL_CLAIM_UNVERIFIED + COMM_WITHDRAWN.
- Both actions append a log entry (kind noted in entry JSON): revocations are logged events, not silent edits.

### 7.5 Optional C2PA (`trust/c2pa_embed.py`)
- `embed(path, entity) -> bool` for jpg/png/mp4 when lib + certs available; `read(path) -> C2PAResult|None` validating against the demo trust anchor only.
- Any exception → log warning, return None/False. The envelope + registry path is the product; C2PA is the standards-alignment garnish.

---

## 8. VERIFICATION PIPELINE & VERDICT ENGINE

### 8.1 Ingest (`pipeline/ingest.py`)
Size caps: image 10 MB, video 64 MB, pdf 20 MB, eml 5 MB, text 20k chars. Sniff MIME with python-magic (never trust extension). Reject oversize/unknown with a clean 422. Store upload to a temp workdir; never execute anything; ffmpeg called with a fixed, argument-listed command (no shell=True).

### 8.2 Hashing (`pipeline/hashing.py`, `pipeline/media.py`)
- Everything: sha256 of raw bytes.
- Images: `imagehash.phash` (64-bit). If `pdqhash` importable, also PDQ-256.
- Video: ffmpeg extracts frames at 1 fps (cap 24 frames, scale longest side 512) → phash each → ordered list.
- PDF: sha256 + extracted text (pypdf) → normalized → SimHash64. Text/SMS/email bodies: normalize (NFKC, lowercase, collapse whitespace, strip zero-width) → SimHash64.
- Implement SimHash64 yourself (~30 lines, token 3-grams) with tests: no flaky dependency.

### 8.3 Matching thresholds (constants in `config.py`)
```
PHASH_MATCH_MAX_DIST = 10        # 64-bit Hamming
PHASH_NEAR_MAX_DIST  = 16
PDQ_MATCH_MAX_DIST   = 31        # 256-bit, only if pdqhash present
VIDEO_FRAME_MATCH_RATIO = 0.55   # fraction of query frames matching any registered frame (dist <= PHASH_MATCH_MAX_DIST)
SIMHASH_MATCH_MAX_DIST = 6
FUZZY_ENTITY_MIN_SCORE = 88      # rapidfuzz token_sort_ratio over sliding token windows, post homoglyph-normalization
```
> **Epic 4 amendment:** uses `token_sort_ratio` over sliding token-length windows, not `token_set_ratio` as originally specified. `token_set_ratio` returns 100 for any token subset match, so a bare "ltd" or "broking" in any message would strong-claim every matching entity. Locked in by a regression test in `test_claims.py`.

Candidate lookup: exact sha256 first; then load published artifacts' hashes (demo scale = full scan is fine; TODO(prod): pgvector/BK-tree).

### 8.4 Claim extraction (`pipeline/claims.py`)
Rule-based (REQUIRED):
1. Normalize input text (caption + body + OCR is out of scope: note it): NFKC, confusable-homoglyphs skeleton, lowercase.
2. Match against entity names, aliases, sebi_reg_nos, registered domains, SMS headers (exact + rapidfuzz ≥ FUZZY_ENTITY_MIN_SCORE).
3. Official-claim markers: mentions of the regulator/exchange demo names, "circular", "registered intermediary", "official", "reg no", header codes, "exchange approved".
4. Output: `{claimed_entity_id: uuid|None, claimed_entity_text: str|None, claim_strength: "none"|"weak"|"strong", evidence: [spans]}`. Strong = named entity match; weak = official markers without a resolvable entity.
LLM path (OPTIONAL, `LLM_ENABLED`): Anthropic messages call returning the same JSON schema (temperature 0, max_tokens 300); on ANY error/timeout(5s) → rule-based result. Cache by text sha in Redis.

### 8.5 Risk signals (`pipeline/risk.py`)
Each detector returns `(reason_code, weight, evidence)`:
- Phrase clusters (regex sets, en + hinglish): guaranteed/assured returns, "X% daily|weekly|monthly", FPI/institutional quota, IPO allotment fee, "pay to unlock withdrawal", urgency ("last 2 hours"), secrecy, Telegram/WhatsApp group invite, APK download.
- Payment ask: UPI VPA regex `[\w.\-]{2,}@[a-z]{2,}`, bank a/c + IFSC pattern, wallet addresses.
- URL risk: punycode/IDN, IP-literal host, shortener list, risky TLD list (.top,.xyz,.icu,.club,.online,.site), http (no TLS), and **lookalike**: Levenshtein ≤ 2 or homoglyph-skeleton match against registered domains → LOOKALIKE_DOMAIN (this one is a fraud-positive, not just risk).
- Blacklist: domain exact, phrase contains, phash within PHASH_MATCH_MAX_DIST of a blacklist phash → BLACKLIST_MATCH (+campaign label).
`RISK_HIGH` composite = LOOKALIKE_DOMAIN or BLACKLIST_MATCH or (payment ask AND ≥2 phrase clusters).

### 8.6 Verdict engine (`pipeline/verdict.py`): ordered, short-circuiting
```
1. HARD BINDING: envelope present (sidecar upload or registry ref) or C2PA manifest readable?
   valid chain + entity active:
     key active                     -> VERIFIED            [SIG_CHAIN_VALID]
     key revoked AFTER issued_at    -> VERIFIED_NOTICE     [KEY_REVOKED_AFTER_SIGNING]
     key revoked BEFORE issued_at   -> add TAMPERED_SIGNATURE, continue to 2
   invalid/tampered                 -> add C2PA_INVALID or TAMPERED_SIGNATURE, continue
2. REGISTRY MATCH: sha256 exact OR phash/pdq/simhash/video-ratio within MATCH thresholds
   against a PUBLISHED communication -> VERIFIED           [HASH_EXACT_MATCH | PHASH_MATCH | SIMHASH_MATCH | VIDEO_MATCH]
   against a REVOKED communication   -> OFFICIAL_CLAIM_UNVERIFIED [COMM_WITHDRAWN]
   near-match only (PHASH_NEAR band) -> add PHASH_NEAR (possible tampered copy), continue
3. CLAIMS + RISK:
   claim (strong|weak) AND any fraud-positive {LOOKALIKE_DOMAIN, BLACKLIST_MATCH,
   TAMPERED_SIGNATURE, TAMPERED_CONTENT, RISK_HIGH}        -> LIKELY_FAKE
   claim (strong|weak), no fraud-positive                  -> OFFICIAL_CLAIM_UNVERIFIED
   no claim, fraud-positive (BLACKLIST_MATCH or URL high)  -> LIKELY_FAKE
   no claim, otherwise                                     -> INFORMATIONAL (attach mild risk notes)
4. ALWAYS: persist verification row + pipeline trace {stage, outcome, ms}; return full result.
```
TAMPERED_CONTENT = input references a specific communication (e.g., pasted certificate link / comm id) but hashes don't match it.

### 8.7 Reason codes (complete enum: implement exactly)
`SIG_CHAIN_VALID, C2PA_VALID, C2PA_MISSING, C2PA_INVALID, TAMPERED_SIGNATURE, TAMPERED_CONTENT, KEY_REVOKED_AFTER_SIGNING, HASH_EXACT_MATCH, PHASH_MATCH, PDQ_MATCH, SIMHASH_MATCH, VIDEO_MATCH, PHASH_NEAR, COMM_WITHDRAWN, ENTITY_CLAIM_STRONG, ENTITY_CLAIM_WEAK, HOMOGLYPH_ENTITY, LOOKALIKE_DOMAIN, DOMAIN_REGISTERED, DOMAIN_NOT_REGISTERED, DKIM_ALIGN_PASS, DKIM_ALIGN_FAIL, AUTH_HEADERS_UNAVAILABLE, BLACKLIST_MATCH, RISK_PHRASES, PAYMENT_ASK, URL_RISK, NO_OFFICIAL_CLAIM`
Each code maps to a localized human string in i18n files.

---

## 9. API CONTRACT (all responses `{ "ok": bool, "data": ..., "error": {code, message} | null }`)

### Verification
- `POST /api/verify`: multipart form. Fields (exactly one content field required): `file` (image/video/pdf/eml) | `text` | `url`. Optional: `claimed_sender_text`, `state_code` (e.g. `IN-KA`), `locale` (`en|hi`), `channel` (default `sim`).
- `GET /api/verifications/{id}`: full stored result.
- `POST /api/verifications/{id}/certificate-token` → `{token, url, expires_at}` (only for VERIFIED / VERIFIED_NOTICE, else 409).

`POST /api/verify` response `data` (this exact shape: the frontend types against it):
```json
{
  "verification_id": "…",
  "verdict": "VERIFIED",
  "headline": "✅ Verified",
  "body": "Issued by Kumaon Metals Ltd (SEBI reg DEMO-INE-000451). Published 10 Jul 2026 via filing. Tamper-evident log entry #14.",
  "reasons": ["PHASH_MATCH", "SIG_CHAIN_VALID"],
  "reason_strings": ["Content matches a registered communication…", "Digital signature chain is valid…"],
  "advice": ["Before paying anyone, verify the payee on SEBI Check."],
  "buttons": [
    {"kind": "certificate", "label": "View certificate", "url": "/c/…"},
    {"kind": "sebi_check", "label": "Verify payee on SEBI Check", "url": "…"}
  ],
  "matched_entity": {"id": "…", "name": "Kumaon Metals Ltd", "sebi_reg_no": "DEMO-INE-000451"},
  "matched_communication": {"id": "…", "title": "Q1 FY27 results filing", "published_at": "…", "log_seq": 14},
  "claimed_entity_text": null,
  "pipeline_trace": [
    {"stage": "hard_binding", "outcome": "no_manifest", "ms": 12},
    {"stage": "registry_match", "outcome": "phash_match_dist_6", "ms": 240},
    {"stage": "claims_risk", "outcome": "skipped_short_circuit", "ms": 0}
  ],
  "locale": "en"
}
```

### Issuer (demo persona via header `X-Demo-Persona: <key_id>`: no real auth; TODO(prod))
- `GET /api/issuer/communications?entity_id=`: list with status.
- `POST /api/issuer/communications`: multipart: `entity_id, title, channel, impact`, `file` | `canonical_text`. Creates draft + artifact (hashes computed now).
- `POST /api/issuer/communications/{id}/sign`: maker persona signs → `maker_signed`.
- `POST /api/issuer/communications/{id}/cosign`: checker persona (required if market_moving) → publish: finalize envelope, optional C2PA embed, append log entry, set `published_at`, return `{log_seq, old_root, new_root}`.
- `POST /api/issuer/communications/{id}/revoke`: withdraw (logs a revocation entry).

### Admin / Registry / Log / Telemetry
- `POST /api/admin/keys/{key_id}/revoke`: body `{reason}`; appends log event.
- `GET /api/registry/entities` | `GET /api/registry/entities/{id}` (with domains, headers, keys+status).
- `GET /api/log/root` → latest STH. `GET /api/log/entries?limit=50`. `GET /api/log/entries/{seq}/proof` → inclusion proof.
- `GET /api/telemetry/summary?window=14d` → `{totals_by_verdict, series_daily, by_state:[{state_code,count_flagged}], top_impersonated:[{entity,count}], campaigns:[{campaign,count,last_seen,channels}]}`.
- `GET /api/c/{token}` → certificate payload; marks token used; expired/used → 410 with a clean error body.
- `GET /healthz` → db + redis status.

Rate limit `POST /api/verify`: 30/min/IP via Redis token bucket (return 429 with retry hint).

---

## 10. FRONTEND SPEC & DESIGN DIRECTION

### 10.1 Design tokens (implement as Tailwind theme extensions + CSS vars)
Palette (no gradients anywhere):
```
--ink:        #0A1B2E   (deep regulatory navy: headers, dark panels)
--paper:      #F7F5F0   (document off-white: app background)
--card:       #FFFFFF
--hairline:   #E4E0D6
--verified:   #0E7C4A   (registry green)
--notice:     #B87A00   (caution amber)
--fake:       #C6362B   (alert vermilion)
--info:       #5B6B7C   (neutral slate)
--seal:       #8A6D1D   (seal gold: tiny accents only: seal icons, active proof step)
```
Typography: Display **Archivo** (600/700, tight tracking) for page titles + verdict headlines only; Body **Inter**; ALL cryptographic material (hashes, key ids, log seq, roots, proofs) in **JetBrains Mono**: mono means machine truth; this is a semantic rule, apply it everywhere without exception. Radius 6px. Shadows minimal (`shadow-sm`). Respect `prefers-reduced-motion` (animations become instant). Responsive to 380px.

### 10.2 Signature element (the one memorable thing: execute this well, keep everything else quiet)
**The pipeline trace + live Merkle proof.** Every verdict card expands to a horizontal three-station trace: Hard binding → Registry match → Claims & risk: rendered like a customs stamp trail: each station shows its actual outcome ("no manifest", "match, distance 6", "skipped") and timing in mono. On the certificate page, the inclusion proof animates hash-by-hash: leaf combines with each audit-path hash, values visibly merging up to the root, ending in a green root-match seal. Verification isn't a badge; you watch it happen.

### 10.3 Verdict cards (component `VerdictCard`)
Styled as **digital seals**: 4px left border in verdict color; seal icon top-right (shield-check / shield-alert / alert-triangle / info); headline in Archivo; body in Inter; mono metadata row (`reg no · published date · log #`); advice lines; buttons (max 3): View certificate / Verify payee on SEBI Check / expand trace. Card copy comes ONLY from the API's localized strings: no frontend-invented text.

### 10.4 Pages
- **/** landing: one-line thesis ("Forward it. We'll tell you if the market actually said it."), live stats strip from telemetry (verifications, flagged today), three seal-style cards linking to Verify / Issuer / Supervision. Footer on EVERY page: "Hackathon prototype: not affiliated with SEBI."
- **/verify**: chat column (max-w-2xl) mimicking a messaging thread. Composer: drag-drop file, paste text, paste URL, upload .eml; optional "claimed sender" input; state dropdown (12 Indian states) for telemetry; en/hi toggle (persists, switches card strings). Submissions render as user bubble → TrustRail verdict-card bubble with expandable PipelineTrace. Empty state invites the three demo actions.
- **/issuer**: persona switcher (seeded maker/checker identities across entities); communications table (status chips: draft / maker-signed / published / revoked); "New communication" drawer (title, channel, impact, file or text). Sign (maker) → Co-sign & publish (checker) → success banner shows `old_root → new_root` in mono ("Log root updated"). Entity detail includes **Simulate key compromise** (calls admin revoke; explanatory banner states exactly what old vs new verifications will now show).
- **/registry**: entity table → detail: kind, reg no, status, domains, SMS headers, keys with status/revoked_at.
- **/log**: STH strip (latest root, tree size); entries table (seq, entity, title, leaf hash); entry detail → **Verify inclusion proof** button runs the TypeScript `verify_inclusion` mirror client-side with the animated combine steps.
- **/supervision**: KPI row (verifications 24h, % flagged, top channel); India choropleth (react-simple-maps + TopoJSON in repo) shaded by flagged count per state, hover tooltips; bar chart of top impersonated entities; campaigns table (campaign, count, last seen, channels). Poll every 10s.
- **/c/[token]**: single-use certificate. Header seal + verdict; entity + reg no; communication title/channel/published_at; artifact sha256 (mono + copy); signature chain summary (maker key, checker key, root); animated Merkle proof; used/expired → clean 410 state explaining one-time links and how to get a fresh one.

Copy register: sentence case, plain verbs, no filler. Buttons say exactly what they do. Errors state what happened and the fix: never apologize vaguely.

---

## 11. I18N: EXACT VERDICT COPY (en + hi complete; both files must cover every card string)

Keys and required strings (`backend/app/i18n/*.json`, mirrored to frontend):
```
verdict.verified.title            en: "✅ Verified"
                                  hi: "✅ सत्यापित"
verdict.verified.body             en: "Issued by {entity} (SEBI reg {reg}). Published {date} via {channel}. Tamper-evident log entry #{seq}."
                                  hi: "{entity} (SEBI पंजीकरण {reg}) द्वारा जारी। {date} को {channel} के माध्यम से प्रकाशित। टैम्पर-एविडेंट लॉग प्रविष्टि #{seq}।"
verdict.verified_notice.title     en: "⚠️ Verified: with notice"
                                  hi: "⚠️ सत्यापित: सूचना के साथ"
verdict.verified_notice.body      en: "Validly signed by {entity} on {date}, but the signing key was revoked on {revoked_date}. Confirm on the entity's official channel before acting."
                                  hi: "{entity} द्वारा {date} को वैध रूप से हस्ताक्षरित, लेकिन हस्ताक्षर कुंजी {revoked_date} को निरस्त कर दी गई। कार्रवाई से पहले संस्था के आधिकारिक चैनल पर पुष्टि करें।"
verdict.official_claim_unverified.title  en: "⚠️ Caution: cannot be confirmed"
                                         hi: "⚠️ सावधान: पुष्टि नहीं हो सकी"
verdict.official_claim_unverified.body   en: "This claims to be from {claimed}, but no registered communication matches. Treat it as unsafe."
                                         hi: "यह {claimed} की ओर से होने का दावा करता है, लेकिन रजिस्ट्री में कोई मेल नहीं मिला। इसे असुरक्षित मानें।"
verdict.likely_fake.title         en: "🚨 High risk: likely fake"
                                  hi: "🚨 उच्च जोखिम: संभवतः नकली"
verdict.likely_fake.body          en: "{top_reason}. Do not act on it. Never pay or share OTPs based on this message."
                                  hi: "{top_reason}। इस पर कार्रवाई न करें। इस संदेश के आधार पर कभी भुगतान न करें और OTP साझा न करें।"
verdict.informational.title       en: "ℹ️ No official claim detected"
                                  hi: "ℹ️ कोई आधिकारिक दावा नहीं मिला"
verdict.informational.body        en: "This doesn't claim to be an official market communication. Stay alert for guaranteed-return promises."
                                  hi: "यह किसी आधिकारिक बाज़ार संचार होने का दावा नहीं करता। गारंटीड रिटर्न के वादों से सावधान रहें।"
advice.sebi_check                 en: "Before paying anyone, verify the payee on SEBI Check."
                                  hi: "किसी को भी भुगतान करने से पहले SEBI Check पर प्राप्तकर्ता सत्यापित करें।"
advice.radar_added                en: "Added to the fraud radar."
                                  hi: "धोखाधड़ी रडार में जोड़ दिया गया।"
button.view_certificate           en: "View certificate"        hi: "प्रमाणपत्र देखें"
button.sebi_check                 en: "Verify payee on SEBI Check"  hi: "SEBI Check पर सत्यापित करें"
button.expand_trace               en: "How this was checked"    hi: "यह कैसे जाँचा गया"
```
Plus a `reasons.{CODE}` string for every reason code in Section 8.7 (en required for all; hi required for the 10 most user-visible: PHASH_MATCH, SIG_CHAIN_VALID, LOOKALIKE_DOMAIN, BLACKLIST_MATCH, ENTITY_CLAIM_STRONG, NO_OFFICIAL_CLAIM, KEY_REVOKED_AFTER_SIGNING, COMM_WITHDRAWN, URL_RISK, PAYMENT_ASK).

---

## 12. CHANNEL ADAPTERS

### 12.1 `channels/render.py` (required)
`render_verdict(result, locale) -> CardPayload`: the ONLY place verdict → human strings mapping happens. Simulator and WhatsApp both consume it. Interpolates i18n templates; picks `top_reason` = highest-weight fraud-positive's string.

### 12.2 `channels/whatsapp.py` + `api/webhooks_whatsapp.py` (flag-gated; Epic 11 only)
- `GET /api/webhooks/whatsapp`: hub.challenge echo with WHATSAPP_VERIFY_TOKEN.
- `POST`: validate `X-Hub-Signature-256` (HMAC app secret). Handle text | image | video | document | audio: download via Graph media endpoint (two-step: media id → URL → bytes), run pipeline synchronously if < 10 MB else reply "checking…" then follow-up.
- Reply with interactive button message (≤ 3 buttons) inside the customer-service window; certificate button carries the one-time URL.
- Write `docs/SETUP_WHATSAPP.md`: Meta app creation, test number, cloudflared/ngrok webhook, env vars. This epic runs ONLY on explicit owner request.

---

## 13. EMAIL PATH (`pipeline/emailcheck.py`)
Accept `.eml` upload (stdlib `email` parser):
1. Extract From, Reply-To, Subject, text body, links, `Authentication-Results` headers.
2. From-domain vs `entity_domains`: DOMAIN_REGISTERED(entity) or DOMAIN_NOT_REGISTERED; homoglyph/Levenshtein sweep → LOOKALIKE_DOMAIN.
3. Parse Authentication-Results if present → DKIM_ALIGN_PASS/FAIL; absent (typical for forwards) → AUTH_HEADERS_UNAVAILABLE with honest copy ("original authentication headers unavailable on forwarded mail").
4. Body + subject → claims + risk; links → URL risk; body → SimHash registry match (a registered email comm can VERIFY).
5. Same verdict engine; email-specific evidence appears in the trace.

---

## 14. TELEMETRY & WEATHER MAP
Every verification persists: verdict, state_code, channel, input_kind, claimed/matched entity, campaign (from blacklist hit; else lookalike-domain string; else null). `/api/telemetry/summary` computes: totals by verdict, daily series (14d), flagged count by state, top impersonated entities (claimed_entity resolution), campaign clusters (group by campaign; fallback bucket PHASH_NEAR neighbors). Supervision page polls this. Seed creates 60 historical rows over 14 days across ≥ 12 states (weighted: MH, KA, RJ, DL, UP, GJ, TN, TS, WB, MP, HR, PB) so the map is alive on first load.

---

## 15. SEED DATA: THE DEMO WORLD (`scripts/seed.py`, idempotent: wipe + rebuild)

### 15.1 Trust material
Demo root ("TrustRail Demo Root: NOT a real authority"), registry STH keypair, maker+checker keypairs for the 3 featured entities, single keys for the rest. P-256 chain only if c2pa importable.

### 15.2 Entities (12: ALL FICTIONAL; sanity-check none collide with real Indian brands)
| Name | Kind | Reg no | Domain | SMS header |
|---|---|---|---|---|
| Demo Securities Board | regulator | DEMO-REG-000001 | demosecboard.example | DSBRD |
| National Demo Exchange (NDX) | exchange | DEMO-EXC-000010 | ndx.example | NDXIN |
| Bharat Demo Exchange (BDX) | exchange | DEMO-EXC-000011 | bdx.example | BDXIN |
| Meridian Broking Ltd ★ | broker | DEMO-INZ-000123 | meridianbroking.example | MERIDN |
| Alpha Capital Services | broker | DEMO-INZ-000124 | alphacapital.example | ALPHCP |
| Suraksha Securities | broker | DEMO-INZ-000125 | surakshasec.example | SURKSH |
| Lotus Investmart | broker | DEMO-INZ-000126 | lotusinvest.example | LOTUSI |
| Kumaon Metals Ltd ★ | listed_company | DEMO-INE-000451 | kumaonmetals.example | KUMAON |
| Vasudha Agrotech Ltd | listed_company | DEMO-INE-000452 | vasudhaagro.example | VASUDH |
| Nivara Housing Finance | listed_company | DEMO-INE-000453 | nivarahf.example | NIVARA |
| Suvarna Mutual Fund ★ | mutual_fund | DEMO-MF-000021 | suvarnamf.example | SUVRNA |
| Aranya Asset Management | mutual_fund | DEMO-MF-000022 | aranyaamc.example | ARANYA |

★ = featured (maker+checker keys; used in the live demo).

### 15.3 Published communications (from `assets_input/`; seed FAILS LOUDLY listing missing files)
Expected owner files: `filing1.pdf, filing2.pdf, filing3.pdf, image1.jpg, image2.jpg, image3.jpg, ceo_announcement.mp4` (+ optional `voice_note.ogg`).
Publish: 3 PDF filings (Kumaon ×2 incl. one market_moving co-signed, Nivara ×1), 3 images (Meridian, Suvarna, NDX), 1 video "Kumaon Metals: CEO announcement" (market_moving, maker+checker), 3 SMS texts (Meridian margin notice, Suvarna NAV update, NDX settlement holiday), 1 email body (Suvarna folio statement notice). Every publish appends a log entry; final tree has ≥ 11 leaves.

### 15.4 Scam fixtures (generated by seed into `var/artifacts/demo/`)
- Tampered copy of Kumaon filing1.pdf (change one revenue figure via pypdf text overlay) → `tampered_filing.pdf`.
- Fake SMS text file: IPO-allotment fee scam claiming Meridian, containing lookalike link `http://rneridianbroking-refunds.top/claim`.
- Fake "official notice" text claiming Demo Securities Board, urgency + UPI payment ask.
- Blacklist rows: domains `rneridianbroking-refunds.top`, `demosecboard-verify.xyz` (campaign "FXROAD-DEMO"); phrase "guaranteed 3% daily returns"; phash of image1 heavily edited (campaign "RECYCLED-CREATIVE").
- A benign news paragraph file (`news_snippet.txt`) mentioning markets generally, no entity claim → must yield INFORMATIONAL.

### 15.5 History + cheat sheet
60 verification rows spread over 14 days/12 states (mix of verdicts, campaigns attached to flagged ones). Seed ends by printing a **DEMO CHEAT SHEET**: exact file paths to forward, persona names for maker/checker, expected verdict per file, and the supervision URL.

---

## 16. EVALUATION HARNESS (`scripts/wa_sim_transform.py`, `scripts/evaluate.py`)

### 16.1 WhatsApp-mangle transforms
Images: JPEG q85 / q70 / q50; resize 0.75 / 0.5; metadata strip; screenshot-sim (5% crop + PNG→JPEG q80). Video: `ffmpeg -i in.mp4 -vf scale=848:-2 -c:v libx264 -crf 26 -preset veryfast -c:a aac -b:a 64k -map_metadata -1` plus a crf30 variant. Text: whitespace/emoji injection + zero-width strip test.

### 16.2 Metrics run (`make eval`, deterministic seed)
Positives: every registered image/video/text under every transform. Negatives: owner's spare images + 30 generated noise images + 20 unrelated text snippets. For each: run full pipeline; record stage outcomes + latency. Write `docs/METRICS.md`:
- Table 1: hard-binding survival per transform (expected: dies on strip/re-encode: state plainly that this is WHY soft binding exists).
- Table 2: registry soft-match precision / recall / F1 per transform + overall.
- Table 3: latency p50/p95 per stage; verdict confusion matrix.
- Targets: precision ≥ 0.95, recall ≥ 0.70. If recall < 0.70: print + write recommendation "lean demo on exact-hash & envelope path" (per research plan).
These numbers are the PS1-required "clear evidence of authentication performance": they go in the pitch deck.

---

## 17. EPICS & GATES (execute in order; STOP at each gate, update PROGRESS.md, commit `Epic N: …`, await owner go)

**Epic 0: Scaffold.** Compose, Makefile, envs, alembic init, FastAPI `/healthz`, Next.js shell with theme tokens + fonts, gitignore. *Gate:* `make up/install/migrate/api/web` all succeed; healthz green.
**Epic 1: Trust core.** `ca.py`, `envelope.py`, `merkle.py` + tests. *Gate:* `pytest tests/test_merkle.py tests/test_envelope.py` green, including: tampered entry → proof fails; wrong key → envelope invalid; checker-required-but-missing → invalid.
**Epic 2: Data model + registry.** Models, migration 001, registry API, seed §15.1–15.2 only. *Gate:* GET /api/registry/entities returns 12 with keys.
**Epic 3: Issuer flow.** Communications CRUD, artifact hashing, sign/cosign/publish → log append, revocations, optional C2PA embed. *Gate:* smoke publishes a PDF end-to-end; log seq increments; STH verifies; revocation endpoints work.
**Epic 4: Pipeline + verdict engine.** ingest/hashing/media/claims/risk/verdict + tests. *Gate:* `tests/test_verdict.py` covers all 5 verdicts, revocation timing both sides, near-match must NOT verify, homoglyph claim case.
**Epic 5: Verify API + tokens + telemetry.** Full §9 verification endpoints, rate limit, view tokens. *Gate:* smoke: publish → wa_sim_transform → verify returns VERIFIED via PHASH_MATCH; second GET of a used token → 410.
**Epic 6: Verify UI.** /verify chat page, VerdictCard, PipelineTrace, en/hi toggle, landing page. *Gate:* manual: drop transformed image → verified seal card; toggle hi → card strings switch.
**Epic 7: Issuer + registry + log UIs.** Personas, maker-checker publish with root-delta banner, key-compromise button, log explorer with client-side proof animation. *Gate:* full publish from UI; proof verifies green in browser.
**Epic 8: Supervision.** KPIs, India choropleth, campaigns table, 10s polling. *Gate:* two fresh flagged verifies appear on map within 10s.
**Epic 9: Email + URL polish.** .eml path per §13; URL risk hardening; seeded sample .eml files. *Gate:* sample forwarded .eml → OFFICIAL_CLAIM_UNVERIFIED with honest auth-headers copy; lookalike-domain SMS text → LIKELY_FAKE.
**Epic 10: Eval + docs + polish.** §16 harness, METRICS.md, DEMO.md, README (with screenshots), ARCHITECTURE.md (mermaid: component + publish/verify sequences + "production path": TrustMark, TMK+PDQF, DLT/exchange ingestion, green tick, HSMs), empty/error states, reduced-motion, favicon. *Gate:* `make demo-reset` then full DEMO.md walkthrough passes without touching code; `make eval` meets targets or writes the documented fallback.
**Epic 11: WhatsApp adapter (ONLY on explicit owner request).** §12.2 + SETUP_WHATSAPP.md. *Gate:* echo + verdict reply on Meta test number.

PROGRESS.md format per epic: `## Epic N: <name> | status | what shipped | deviations from spec (+why) | how gate was verified | next`.

---

## 18. DEMO RUNBOOK (`DEMO.md`: write this file verbatim-precise during Epic 10)
0. `make demo-reset` (prints cheat sheet). Two browser windows: /issuer + /verify; third tab /supervision.
1. Issuer: as Kumaon maker, create "CEO announcement" (video, market_moving) → Sign. Switch persona to checker → Co-sign & publish → point at the root-delta banner.
2. Terminal: `python -m scripts.wa_sim_transform var/artifacts/<video>.mp4 --preset whatsapp` → produces mangled copy (metadata stripped, re-encoded).
3. /verify: drop the MANGLED video → ✅ Verified card → expand "How this was checked" (hard binding: no manifest → registry match: video frames matched) → open certificate → watch Merkle proof animate.
4. /verify: drop `tampered_filing.pdf` with claimed sender "Kumaon Metals" → 🚨 High risk (claim + no match + PHASH_NEAR tamper hint).
5. /verify: paste the fake IPO SMS text → 🚨 (LOOKALIKE_DOMAIN + PAYMENT_ASK + blacklist campaign) → verdict names the campaign.
6. /verify: drop `news_snippet.txt` → ℹ️ Informational (the base-rate answer: narrate this to judges).
7. /supervision: both flags are on the map; campaigns table shows FXROAD-DEMO.
8. /issuer → Kumaon → Simulate key compromise → re-verify the step-3 video → ⚠️ Verified with notice; /log shows the revocation entry; nothing was silently rewritten.
Contingency: if anything breaks live, `make demo-reset` restores in < 60s; keep a screen recording of a full pass as backup.

---

## 19. DOCS TO PRODUCE
README.md (what/why in 6 lines, quickstart, screenshots, demo pointer), docs/ARCHITECTURE.md (mermaid diagrams + production path section + explicit "what is mocked vs real" table), docs/METRICS.md (generated), DEMO.md, PROGRESS.md, docs/SETUP_WHATSAPP.md (Epic 11 only).

---

## 20. GUARDRAILS & OUT OF SCOPE
- A unit test MUST enforce: no code path emits VERIFIED without (valid chain) or (registry match to published comm). Treat any violation as a release blocker.
- Fictional entities only; no real brands, tickers, or persons in fixtures or copy. The demo video is the owner's own footage. Never generate or include deepfakes of real people.
- UI vocabulary: "digital signature", "tamper-evident log", "maker-checker approval". Banned words in UI: blockchain, crypto, ledger, multi-sig, token (user-facing).
- No invented numbers anywhere in UI; all stats come from the DB.
- Every page footer: "Hackathon prototype: not affiliated with SEBI."
- Out of scope for code (ARCHITECTURE.md "production path" only): TrustMark watermarking, TMK+PDQF, real NSE/BSE/DLT integration, WhatsApp green tick, HSM key custody, OCR.
- Performance budget on a dev laptop: verify p95 < 3s (images/text) / < 8s (video). If a dependency fights you > 30 minutes, implement the documented fallback and record it in PROGRESS.md.

END OF SPEC. After the owner confirms, begin with Epic 0.
