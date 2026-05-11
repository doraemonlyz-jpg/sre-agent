#!/usr/bin/env bash
# Generate enough load on the chaos-app to trigger the redis connection-pool
# "leak" bug. After ~50 calls /redis-leak starts returning 500s with the
# same ConnectionError messages the SRE Agent looks for.
#
# Usage:
#   ./scripts/generate-load.sh [count] [target_url]
#
# Defaults: 80 calls against http://localhost:8000

set -euo pipefail

COUNT="${1:-80}"
TARGET="${2:-http://localhost:8000}"

echo "→ Hitting $TARGET/redis-leak $COUNT times"
for i in $(seq 1 "$COUNT"); do
  curl -s -o /dev/null -w "%{http_code} " "$TARGET/redis-leak"
  if (( i % 20 == 0 )); then echo " (i=$i)"; fi
done
echo ""
echo "✓ Done. The leak counter should be at $COUNT."
echo "  Hits to /redis-leak past the limit return 500 with redis.exceptions.ConnectionError."
echo ""
echo "Next:  ./scripts/fire-alert.sh"
