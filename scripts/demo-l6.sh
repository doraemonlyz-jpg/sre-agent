#!/usr/bin/env bash
#
# scripts/demo-l6.sh — end-to-end L6 flywheel demo.
#
# Walks through the four moves that make the system look like a real
# self-improving SRE agent rather than a vanity dashboard:
#
#   1. Seed 2000 synthetic incidents (with realistic feedback +
#      a prompt A/B split where the variant outperforms baseline).
#   2. Boot the dashboard against the seeded state.
#   3. Curl the L5 telemetry endpoints (feedback, harness, readiness)
#      to show what an oncall would see.
#   4. Run the L6 winner-promotion analyzer + auto-runbook drafter
#      against the same data, producing two Markdown deliverables you
#      could drop into a real PR.
#
# Re-runnable. Cleans up its own dashboard process at the end (unless
# you set DEMO_KEEP=1 to leave it running for manual exploration).
#
# Usage:
#   bash scripts/demo-l6.sh            # full run, dashboard exits at end
#   DEMO_KEEP=1 bash scripts/demo-l6.sh  # leave dashboard up for poking
#   DEMO_N=5000 bash scripts/demo-l6.sh  # bigger corpus
#
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

# ── config ───────────────────────────────────────────────────────────
# Defaults sized to land on a statistically significant "promote"
# decision so the demo tells a complete story. Lower DEMO_N to see the
# system correctly HOLD on thin evidence (also a valid demo —
# "the system refuses to promote on a vibe").
DEMO_N="${DEMO_N:-3000}"
DEMO_PORT="${DEMO_PORT:-5099}"
DEMO_STATE="${DEMO_STATE:-/tmp/sre-l6-demo}"
DEMO_AB="${DEMO_AB:-0.3}"
DEMO_RNG="${DEMO_RNG:-42}"
DEMO_KEEP="${DEMO_KEEP:-0}"
OUT_DIR="${OUT_DIR:-${DEMO_STATE}/reports}"

# ── colours ──────────────────────────────────────────────────────────
GREEN="$(printf '\033[1;32m')"
YELLOW="$(printf '\033[1;33m')"
CYAN="$(printf '\033[1;36m')"
DIM="$(printf '\033[2m')"
RESET="$(printf '\033[0m')"

banner() { printf "\n${CYAN}== %s ==${RESET}\n" "$1"; }
ok()     { printf "${GREEN}✓${RESET} %s\n" "$1"; }
note()   { printf "${DIM}  %s${RESET}\n" "$1"; }

# ── 0. Fresh state ───────────────────────────────────────────────────
banner "Step 0 — Reset demo state"
rm -rf "${DEMO_STATE}"
mkdir -p "${DEMO_STATE}/feedback" "${OUT_DIR}"
ok "wiped ${DEMO_STATE}"

# Stop any pre-existing dashboard on the demo port. (The L6 demo runs
# in isolation; piggy-backing on a stale process produces confusing
# results because the seed-on-boot only fires for a fresh app.)
pkill -9 -f "dashboard/app.py" >/dev/null 2>&1 || true
sleep 1

# ── 1. Boot dashboard with seed-on-boot ──────────────────────────────
banner "Step 1 — Boot dashboard with ${DEMO_N} seeded incidents"
SRE_STATE_DIR="${DEMO_STATE}" \
SRE_FEEDBACK_DIR="${DEMO_STATE}/feedback" \
SRE_PROVIDER=mock \
SRE_DASHBOARD_PORT="${DEMO_PORT}" \
SRE_SEED_ON_BOOT="${DEMO_N}" \
SRE_SEED_RNG_SEED="${DEMO_RNG}" \
SRE_SEED_AB_FRACTION="${DEMO_AB}" \
OLLAMA_BASE_URL="http://127.0.0.1:1" \
nohup python dashboard/app.py > "${DEMO_STATE}/dashboard.log" 2>&1 &
DASH_PID=$!
note "dashboard pid=${DASH_PID}, log=${DEMO_STATE}/dashboard.log"

# Wait until the readiness probe goes green or 30s timeout.
for i in $(seq 1 30); do
  if curl -sS -m 1 "localhost:${DEMO_PORT}/api/readiness" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
ok "dashboard up on http://localhost:${DEMO_PORT}"

# ── 2. Hit the telemetry surface ─────────────────────────────────────
banner "Step 2 — Telemetry surface (what oncall sees)"
echo "  /api/readiness:"
curl -sS "localhost:${DEMO_PORT}/api/readiness" | python -m json.tool | sed 's/^/    /'
echo
echo "  /api/feedback/summary:"
curl -sS "localhost:${DEMO_PORT}/api/feedback/summary" | python -m json.tool | sed 's/^/    /'
echo
echo "  /api/harness/summary (recorder block):"
curl -sS "localhost:${DEMO_PORT}/api/harness/summary" \
  | python -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d['recorder'], indent=2))" \
  | sed 's/^/    /'

# ── 3. Winner promotion ──────────────────────────────────────────────
banner "Step 3 — L6.1 winner promotion (from feedback + prompt SHAs)"
SRE_FEEDBACK_DIR="${DEMO_STATE}/feedback" \
python -m sre_agent.cli winner \
  --baselines "hypothesis-gen=0c8f14d5" \
  --out-md "${OUT_DIR}/winner.md" \
  --out-json "${OUT_DIR}/winner.json" \
  >/dev/null
ok "wrote ${OUT_DIR}/winner.md"
echo
sed -n '1,40p' "${OUT_DIR}/winner.md"
echo
note "(full report at ${OUT_DIR}/winner.md)"

# Pull the headline verdict + delta from JSON, no jq required.
SUMMARY=$(SRE_FEEDBACK_DIR="${DEMO_STATE}/feedback" python -c "
import json
d = json.load(open('${OUT_DIR}/winner.json'))
for dec in d['decisions']:
    if dec['agent'] == 'hypothesis-gen':
        print(f\"{dec['verdict']}  delta={dec['delta_pp']:+.1f}pp  p={dec['p_value']:.4f}\")
        break
")
echo
${YELLOW:+printf "${YELLOW}headline: %s${RESET}\n" "$SUMMARY"}

# ── 4. Auto-runbook drafter ──────────────────────────────────────────
banner "Step 4 — L6.1 auto-runbook drafter (from oncall corrections)"
SRE_FEEDBACK_DIR="${DEMO_STATE}/feedback" \
python -m sre_agent.cli autorunbook \
  --min-occurrences 8 \
  --out-md "${OUT_DIR}/runbook-draft.md" \
  >/dev/null
ok "wrote ${OUT_DIR}/runbook-draft.md"
echo
sed -n '1,35p' "${OUT_DIR}/runbook-draft.md"
note "(full draft at ${OUT_DIR}/runbook-draft.md)"

# ── 5. Summary ───────────────────────────────────────────────────────
banner "Done"
echo "  Seeded: ${DEMO_N} incidents (RNG ${DEMO_RNG}, A/B ${DEMO_AB})"
echo "  Dashboard: http://localhost:${DEMO_PORT}"
echo "  Reports: ${OUT_DIR}/"
echo "    - winner.md         : prompt promotion decision"
echo "    - winner.json       : same, machine-readable"
echo "    - runbook-draft.md  : auto-clustered oncall corrections"
echo

if [[ "${DEMO_KEEP}" = "1" ]]; then
  ok "DEMO_KEEP=1 set — dashboard left running (pid ${DASH_PID})"
  echo "  Stop with: kill ${DASH_PID}"
else
  kill "${DASH_PID}" 2>/dev/null || true
  ok "dashboard stopped"
fi
