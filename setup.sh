#!/usr/bin/env bash
# SRE Agent v1 — one-shot local setup.
# Idempotent. Re-run any time.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${SRE_DASHBOARD_PORT:-${SRE_PORT:-5080}}"   # 5060 is blocked by Chrome (SIP)

echo "──────────────────────────────────────────────────────────"
echo "  SRE Command Center — v1 (LangGraph)"
echo "──────────────────────────────────────────────────────────"
echo

# 1. python venv at repo root (used by all components)
if [[ ! -d "$HERE/.venv" ]]; then
  echo "▶ creating python venv"
  python3 -m venv "$HERE/.venv"
fi

echo "▶ installing sre-agent + dependencies (this may take a minute)"
"$HERE/.venv/bin/pip" install --quiet --upgrade pip
"$HERE/.venv/bin/pip" install --quiet -e "$HERE"

# 2. kill any stale instance
if lsof -ti:"$PORT" >/dev/null 2>&1; then
  echo "▶ killing stale instance on :$PORT"
  lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true
  sleep 1
fi

# 3. start dashboard
echo "▶ starting dashboard on http://127.0.0.1:$PORT"
nohup "$HERE/.venv/bin/python" "$HERE/dashboard/app.py" \
  > /tmp/sre-dashboard.log 2>&1 &
DASH_PID=$!
echo "$DASH_PID" > /tmp/sre-dashboard.pid

# 4. wait until /api/health responds
for i in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    echo "▶ dashboard ready"
    break
  fi
  sleep 0.5
done

# 5. summary
echo
echo "✓ Dashboard up: http://127.0.0.1:$PORT"
echo "  pid:  $DASH_PID"
echo "  log:  /tmp/sre-dashboard.log"
echo
echo "Open the URL and click  +FIRE ALERT  to run a demo incident."
echo
echo "Or use the CLI:"
echo "  source .venv/bin/activate"
echo "  sre-agent scenarios"
echo "  sre-agent investigate --scenario redis-pool-exhaustion"
echo
echo "Stop with:   kill \$(cat /tmp/sre-dashboard.pid)"
