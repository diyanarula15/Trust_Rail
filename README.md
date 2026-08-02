# TrustRail

Investors forward suspicious market content, such as a video, a PDF
filing, an SMS, an email, or a link, and TrustRail answers whether a SEBI-registered
entity actually issued it. Cryptographic provenance first (a signed,
tamper-evident transparency log), perceptual/content matching second
(survives WhatsApp-style re-encoding), risk heuristics last, and it never
says "verified" without one of the first two actually proving it.

Built for the SEBI Securities Market TechSprint 2026, Problem Statement 1.
Hackathon prototype, not affiliated with SEBI. Fictional entities only.

## Quickstart

Prerequisites: Docker, Python 3.11+, Node 20+ with pnpm, `ffmpeg` on PATH.

```bash
docker compose up -d --wait                        # postgres + redis

cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # Scripts/ on Windows
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed                    # needs assets_input/ populated, see below

cd ../frontend
pnpm install
pnpm dev                                            # http://localhost:3000

# separate terminal:
cd backend && .venv/bin/uvicorn app.main:app --port 8000
```

`scripts/seed.py` fails loudly and lists exactly what's missing if
`assets_input/` (gitignored, owner-provided media, never committed) isn't
populated with `filing1.pdf, filing2.pdf, filing3.pdf, image1.jpg,
image2.jpg, image3.jpg, ceo_announcement.mp4`.

`make check` / `make eval` exist for machines with `make` installed; on
this dev machine (Windows, no `make`) the underlying commands are run
directly. See `Makefile` for exactly what each target chains, and
PROGRESS.md's "Epic 5 pre-flight" entry for the Windows-specific setup
notes (port conflicts, `python-magic`, console encoding).

## Screenshots

Not yet captured in this repo. This build was verified end to end via
direct API calls and a live in-browser check by the project owner (see
PROGRESS.md, Epic 6), but no automated browser-screenshot tooling was
available in this environment. Run `pnpm dev` and walk DEMO.md to see it
live; screenshots are a good addition for the submission deck.

## Demo

**[DEMO.md](DEMO.md)** is the exact 8-step runbook: reset, publish live,
mangle a video like WhatsApp would, verify it still checks out, a tampered
filing, a lookalike-domain scam SMS, a plain news paragraph, the
supervision map, and a key revocation. Written to be followed by someone
who has never seen the code.

**[docs/METRICS.md](docs/METRICS.md)** has the real precision/recall
numbers from `scripts/evaluate.py`. This is the "evidence of
authentication performance" the problem statement asks for.

**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** has the component and
sequence diagrams, plus an explicit "what's mocked vs. real" table and the
production-path notes (TrustMark, TMK+PDQF, real exchange ingestion, HSM
custody) for what this prototype deliberately doesn't build.

**[PROGRESS.md](PROGRESS.md)** is the epic-by-epic build log: what
shipped, every deviation from the original spec and why, and how each
epic's gate was actually verified.

## Stack

FastAPI + SQLAlchemy + Postgres + Redis on the backend; Next.js 14 (App
Router) + TypeScript + Tailwind on the frontend. Ed25519 signatures
(PyNaCl), an RFC 6962-style transparency log, and a TypeScript mirror of
the log's inclusion-proof verification (`frontend/src/lib/merkle.ts`) that
runs client-side, tested against the same fixture the Python side is
tested against (`fixtures/merkle_vectors.json`).
