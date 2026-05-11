#!/usr/bin/env bash
# Fire an alert at the SRE Agent dashboard's webhook endpoint. This is what
# a real Datadog Monitor / PagerDuty trigger / Alertmanager rule would do.
#
# Usage:
#   ./scripts/fire-alert.sh [dashboard_url]
#
# Defaults to http://localhost:5080.

set -euo pipefail

DASH="${1:-http://localhost:5080}"

PAYLOAD=$(cat <<'JSON'
{
  "service": "chaos-app",
  "description": "error rate spiking on chaos-app — possible connection pool exhaustion",
  "severity": "P2",
  "tags": ["env:demo", "service:chaos-app"]
}
JSON
)

echo "→ POST $DASH/api/alerts/webhook"
echo "$PAYLOAD" | jq . 2>/dev/null || echo "$PAYLOAD"
echo ""

RESP=$(curl -fsS -X POST "$DASH/api/alerts/webhook" \
  -H "Content-Type: application/json" \
  -H "X-SRE-Source: generic" \
  -d "$PAYLOAD")

echo "← $RESP"
echo ""

if INC_ID=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])" 2>/dev/null); then
  echo "✓ Investigation started — incident id $INC_ID"
  echo "  Watch it live:  $DASH"
fi
