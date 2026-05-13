#!/usr/bin/env bash
#
# End-to-end smoke test against a running dashboard.
#
# What it does:
#   1. Verifies /api/health and /api/readiness return ok.
#   2. Fires one incident, polls until diagnosed.
#   3. Submits thumbs-up feedback, reads it back.
#   4. Submits a Slack-action payload (no signature; the server has
#      verification off by default).
#   5. Checks the harness summary surfaces every subsystem.
#   6. Hits /api/prompts/variants to confirm A/B endpoint serves data.
#
# Usage:
#   scripts/smoke.sh                          # against http://localhost:5050
#   BASE=http://localhost:9000 scripts/smoke.sh
#   AUTH_TOKEN=tok-xyz scripts/smoke.sh       # if auth is on
#
# Exit codes: 0 = smoke passed, non-zero = something broke.

set -euo pipefail

BASE="${BASE:-http://localhost:5050}"
AUTH_TOKEN="${AUTH_TOKEN:-}"

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
blue()   { printf "\033[34m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }

curl_json() {
  if [[ -n "$AUTH_TOKEN" ]]; then
    curl -sS -H "Authorization: Bearer $AUTH_TOKEN" -H "Content-Type: application/json" "$@"
  else
    curl -sS -H "Content-Type: application/json" "$@"
  fi
}

step() {
  blue ""
  blue "▸ $*"
}

step "1/8 — /api/health"
HEALTH=$(curl_json "$BASE/api/health")
echo "$HEALTH" | head -c 200
echo
echo "$HEALTH" | grep -q '"ok": *true' && green "  ok=true" || { red "  health failed"; exit 1; }

step "2/8 — /api/readiness (deep)"
READ=$(curl_json "$BASE/api/readiness")
echo "$READ" | head -c 400
echo
echo "$READ" | grep -q '"ok": *true' && green "  ready" || { red "  not ready"; exit 1; }

step "3/8 — POST /api/incidents/fire"
FIRE_BODY='{"service":"checkout-api","severity":"SEV-2","description":"p99 latency 3.4s, error rate 8%"}'
FIRE_RESP=$(curl_json -X POST "$BASE/api/incidents/fire" -d "$FIRE_BODY")
echo "$FIRE_RESP"
INCIDENT_ID=$(echo "$FIRE_RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
green "  incident_id=$INCIDENT_ID"

step "4/8 — poll /api/incidents/$INCIDENT_ID until diagnosed (max 60s)"
for i in $(seq 1 60); do
  STATUS=$(curl_json "$BASE/api/incidents/$INCIDENT_ID" | python3 -c 'import sys,json; print(json.load(sys.stdin)["phase"])')
  if [[ "$STATUS" == "diagnosed" || "$STATUS" == "no_signal" ]]; then
    green "  reached phase=$STATUS after ${i}s"
    break
  fi
  printf "."
  sleep 1
done
if [[ "$STATUS" != "diagnosed" && "$STATUS" != "no_signal" ]]; then
  red "  pipeline did not converge (still $STATUS); aborting"
  exit 1
fi

step "5/8 — POST /api/incidents/$INCIDENT_ID/feedback"
FB_RESP=$(curl_json -X POST "$BASE/api/incidents/$INCIDENT_ID/feedback" \
  -d '{"verdict":"thumbs_up","submitter":"smoke-test","free_text":"looks right"}')
echo "$FB_RESP"
echo "$FB_RESP" | grep -q '"ok"' && green "  feedback accepted" || { red "  feedback rejected"; exit 1; }

step "6/8 — GET /api/incidents/$INCIDENT_ID/feedback (round-trip)"
GET_FB=$(curl_json "$BASE/api/incidents/$INCIDENT_ID/feedback")
echo "$GET_FB" | head -c 240
echo
echo "$GET_FB" | grep -q '"submitter": *"smoke-test"' && green "  round-trip OK" || { red "  feedback not persisted"; exit 1; }

step "7/8 — POST /api/slack/actions (thumbs up)"
PAYLOAD=$(python3 -c "import json; print(json.dumps({'actions':[{'action_id':'sre_feedback_up','value':'$INCIDENT_ID'}], 'user':{'username':'smoke-slack'}}))")
SLACK_RESP=$(curl -sS -X POST -d "payload=$PAYLOAD" "$BASE/api/slack/actions")
echo "$SLACK_RESP"
echo "$SLACK_RESP" | grep -q '"verdict": *"thumbs_up"' && green "  slack action accepted" || { red "  slack action failed"; exit 1; }

step "8/8 — /api/harness/summary surfaces all subsystems"
SUMM=$(curl_json "$BASE/api/harness/summary")
for key in recorder cache rate_limit feedback observability; do
  echo "$SUMM" | grep -q "\"$key\"" || { red "  missing $key"; exit 1; }
done
green "  recorder/cache/rate_limit/feedback/observability all present"

step "extra — /api/prompts/variants"
curl_json "$BASE/api/prompts/variants" | head -c 200
echo

green ""
green "ALL SMOKE CHECKS PASSED."
