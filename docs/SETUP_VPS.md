# Deploying the backend to a VPS

The frontend already lives on Vercel. This covers the backend: the API
(including the SMS webhook), Postgres, Redis, and the Telegram/Gmail
pollers, all on one small VPS via `docker-compose.prod.yml`.

Chosen over Render/Railway because both meter or cap continuous usage
(Render's free tier sleeps; Railway's free/trial credit doesn't cover five
always-on services for long) - a $4-6/mo VPS (Hetzner, DigitalOcean, etc.)
runs everything for a flat fee with no credit to watch.

## 1. Provision the VPS

Any small Ubuntu 22.04/24.04 box (1-2 vCPU, 2GB+ RAM) works. Install
Docker:

```
curl -fsSL https://get.docker.com | sh
```

(Docker Compose v2 ships as the `docker compose` plugin with that installer
- no separate install needed.)

## 2. Point a domain at it

Add an `A` record: `api.yourdomain.com` -> the VPS's public IP. Needed for
Caddy to obtain a real HTTPS certificate (Twilio's SMS webhook requires
valid HTTPS; Telegram/Gmail polling don't strictly need it, but everything
sits behind the same proxy here). This is the same domain you'll eventually
want for the BIMI/DMARC track, so it's not a one-off purchase.

## 3. Clone the repo and configure secrets

```
git clone https://github.com/diyanarula15/Trust_Rail
cd Trust_Rail
cp .env.example .env
```

Edit `.env`:
- Add `API_DOMAIN=api.yourdomain.com` (Caddy reads this).
- Fill in `BASE_URL` with your Vercel frontend URL, `API_BASE_URL` with
  `https://api.yourdomain.com`.
- **Change `POSTGRES_PASSWORD` in `docker-compose.yml`** away from the
  default committed value (it's public on GitHub) and update
  `DATABASE_URL` in `.env` to match.
- Add Telegram/Gmail/Twilio credentials as you set each one up (see
  `docs/SETUP_TELEGRAM.md`, `docs/SETUP_EMAIL.md`, `docs/SETUP_SMS.md`) -
  or leave a channel's block blank and it ships simulated until you're
  ready for it.

`.env` is gitignored - never commit it.

## 4. Bring it up

```
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

This starts Postgres, Redis, the API (behind Caddy on 80/443), and both
pollers, all with `restart: unless-stopped`. `alembic upgrade head` runs
automatically on the backend's boot (Dockerfile CMD); the two pollers also
run it on their own boot before polling, so migrations apply regardless of
start order.

Check it came up:

```
docker compose ps
curl https://api.yourdomain.com/healthz
```

## 5. Seed the registry (once)

Unlike a PaaS with a per-service Docker build context, everything is one
checkout here, so this can run directly on the host instead of needing a
workaround:

```
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DATABASE_URL=postgresql+psycopg://trustrail:<your-password>@localhost:5434/trustrail \
  .venv/bin/python -m scripts.seed
```

`scripts/seed.py` fails loudly and lists exactly what's missing if it needs
files you haven't provided - see the README's Quickstart section.

## 6. Point the frontend at it

In Vercel's project settings, set the API URL env var to
`https://api.yourdomain.com` and redeploy.

## 7. Go live per channel

Now follow the "Going live" section of `docs/SETUP_TELEGRAM.md`,
`docs/SETUP_EMAIL.md`, and `docs/SETUP_SMS.md` - the credentials go in this
VPS's `.env`, then:

```
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

again to pick them up (only the changed services actually restart).

## Gotchas

- **`db`/`redis` are bound to `127.0.0.1` in the prod overlay**, not the
  public interface - reachable from the host itself (step 5) or over SSH
  tunnel, not from the internet. Don't remove that binding.
- **`var/trust` and `var/artifacts` live on the `trustrail_var` named
  volume**, shared by the API and both pollers since they're all on the
  same host. Back this volume up - losing it re-mints the signing keys and
  invalidates every certificate link and log entry issued so far, same as
  the PaaS disk warning in `render.yaml`.
- **Redeploying** is `git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.
  Compose only rebuilds/restarts services whose image or config actually
  changed.
