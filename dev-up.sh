#!/usr/bin/env bash
# One-command startup for local dev on this Windows machine, where `make`
# isn't installed and the Makefile's POSIX `.venv/bin` paths don't exist
# anyway (see Makefile's own comments). Run from the repo root in Git Bash:
#
#   ./dev-up.sh
#
# What it actually does, in order, and why each step exists:
#   1. Confirms Docker Desktop is reachable (it must already be running —
#      launching a GUI app from a script isn't reliable, so this just fails
#      fast with a clear message instead of hanging).
#   2. Brings up Postgres/Redis. `docker compose up -d` fails with a naming
#      conflict if the containers already exist but stopped (happens every
#      time this machine sleeps/restarts) rather than starting them, so this
#      falls back to `docker start` on that exact failure.
#   3. Kills anything already listening on 8000/3000. TaskStop-ing a
#      previous `pnpm dev`/uvicorn run has repeatedly left the real Node/
#      Python process orphaned and still holding the port — killing by port
#      is what's actually proven reliable this session, not trusting a
#      stored job PID.
#   4. Starts backend + frontend in the background, logging to
#      .dev-backend.log / .dev-frontend.log, and polls both /healthz and
#      the frontend root until they actually respond (first Next.js compile
#      can take 10-15s) instead of declaring victory immediately.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

kill_port() {
  local port="$1" pid
  pid=$(netstat -ano 2>/dev/null | grep ":$port " | grep LISTENING | awk '{print $NF}' | head -1)
  if [ -n "${pid:-}" ]; then
    echo "  stale process on port $port (PID $pid) — stopping it"
    powershell -NoProfile -Command "Stop-Process -Id $pid -Force" >/dev/null 2>&1 || true
    sleep 1
  fi
}

echo "== Docker =="
if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop doesn't seem to be running. Start it, then re-run ./dev-up.sh." >&2
  exit 1
fi
if ! docker compose up -d --wait 2>/tmp/dev-up-compose.log; then
  echo "  compose up hit a conflict (containers likely exist but stopped) — starting them directly"
  docker start trustrail-db trustrail-redis >/dev/null
fi
for name in trustrail-db trustrail-redis; do
  for _ in $(seq 1 30); do
    status=$(docker inspect -f '{{.State.Health.Status}}' "$name" 2>/dev/null || echo "")
    [ "$status" = "healthy" ] && break
    sleep 1
  done
  echo "  $name: $(docker inspect -f '{{.State.Health.Status}}' "$name" 2>/dev/null || echo unknown)"
done

echo "== Backend (port 8000) =="
kill_port 8000
cd "$ROOT/backend"
PYTHONUTF8=1 .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 > "$ROOT/.dev-backend.log" 2>&1 &
disown
cd "$ROOT"

echo "== Frontend (port 3000) =="
kill_port 3000
cd "$ROOT/frontend"
pnpm dev > "$ROOT/.dev-frontend.log" 2>&1 &
disown
cd "$ROOT"

echo "== Waiting for backend =="
backend_ok=false
for _ in $(seq 1 30); do
  if curl -s -m 2 http://localhost:8000/healthz 2>/dev/null | grep -q '"ok":true'; then
    backend_ok=true
    break
  fi
  sleep 1
done
if [ "$backend_ok" = true ]; then
  echo "  backend: OK (http://localhost:8000)"
else
  echo "  backend did not become healthy in time — check .dev-backend.log" >&2
fi

echo "== Waiting for frontend (first compile can take a while) =="
frontend_ok=false
for _ in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 2 http://localhost:3000 2>/dev/null || echo "000")
  if [ "$code" = "200" ]; then
    frontend_ok=true
    break
  fi
  sleep 1
done
if [ "$frontend_ok" = true ]; then
  echo "  frontend: OK (http://localhost:3000)"
else
  echo "  frontend did not respond in time — check .dev-frontend.log" >&2
fi

echo
echo "Logs: .dev-backend.log / .dev-frontend.log"
echo "Stop everything with: ./dev-down.sh"
