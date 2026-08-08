#!/usr/bin/env bash
# Stops whatever dev-up.sh started. Kills by port rather than by stored PID
# — this session repeatedly proved that a background job's own PID isn't
# reliably the actual Node/Python process holding the port (bash forks an
# intermediate shell), so port-based lookup is the only thing that's
# actually worked. Leaves Docker containers running (they're cheap to keep
# up, and stopping/starting them isn't the friction this exists to remove).
set -uo pipefail

kill_port() {
  local port="$1" pid
  pid=$(netstat -ano 2>/dev/null | grep ":$port " | grep LISTENING | awk '{print $NF}' | head -1)
  if [ -n "${pid:-}" ]; then
    echo "Stopping process on port $port (PID $pid)"
    powershell -NoProfile -Command "Stop-Process -Id $pid -Force" >/dev/null 2>&1 || true
  else
    echo "Nothing listening on port $port"
  fi
}

kill_port 8000
kill_port 3000
echo "Done. (Postgres/Redis containers left running — 'docker compose stop' if you want those down too.)"
