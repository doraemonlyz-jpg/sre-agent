# SRE Agent — open-source demo stack

A self-contained world where the SRE Agent runs against **real** observability
infrastructure (Prometheus + Loki + Grafana) instrumenting a deliberately
buggy service. Bring it up, push load until it breaks, fire a webhook, and
watch the multi-agent investigation surface the root cause in seconds.

This is the demo to record for an interview.

---

## What's in the stack

| Service     | Port | Role                                                |
|-------------|------|-----------------------------------------------------|
| `chaos-app` | 8000 | Flask service with deliberate bugs (see below)      |
| `prometheus`| 9090 | Scrapes `chaos-app:8000/metrics` every 5s           |
| `loki`      | 3100 | Stores logs the chaos-app pushes directly via HTTP  |
| `grafana`   | 3000 | Anonymous-admin Grafana, both datasources wired up  |

The chaos-app exposes:

| Endpoint         | Behaviour                                                    |
|------------------|--------------------------------------------------------------|
| `GET /healthy`   | always 200 — baseline                                        |
| `GET /slow`      | sleeps 100-2000ms then 200 — latency noise                   |
| `GET /crash`     | 5% chance of 500 — background error rate                    |
| `GET /redis-leak`| leaks a "connection" per call; **after 50 calls the pool is exhausted and every subsequent call returns 500 with `redis.exceptions.ConnectionError: Connection refused`** |
| `POST /admin/reset` | reset the leak counter (start over)                       |
| `GET /metrics`   | Prometheus exposition                                        |

The 50-call threshold is the signature bug the SRE Agent is designed to
detect: a clear before/after correlation across logs (specific error strings),
metrics (error_rate spike), and a custom metric (`chaos_redis_connections`
climbing monotonically).

---

## 60-second demo recipe

```bash
# 1. Bring the stack up (~30s on first pull)
docker compose -f demo-stack/docker-compose.yml up -d --build

# 2. Point the SRE Agent at the stack
export SRE_DATA_PROVIDER=oss
export PROMETHEUS_URL=http://localhost:9090
export LOKI_URL=http://localhost:3100

# 3. Start the dashboard (separate terminal)
python dashboard/app.py
# → http://localhost:5080

# 4. Generate load. After ~50 calls, chaos-app starts failing.
./demo-stack/scripts/generate-load.sh 80

# 5. Fire the alert webhook
./demo-stack/scripts/fire-alert.sh

# 6. Open the dashboard. Watch 7 agents fan out, hit real Prometheus + real
#    Loki, produce a ranked hypothesis (connection-pool exhaustion) with
#    confidence + supporting evidence.
open http://localhost:5080
```

When the demo is done:

```bash
docker compose -f demo-stack/docker-compose.yml down -v
```

---

## What the SRE Agent will say

With the chaos-app over-threshold, the investigation produces:

```
Logs   FOUND  82 hits — top: redis.exceptions.ConnectionError (×31)
Metrics FOUND error_rate baseline 0.1 → peak 4.6 (SPIKE 46x)
                latency_p99 baseline 12ms → peak 1.8s (SPIKE 150x)
Traces NO_SIGNAL  (no tracing wired up in this demo)
Deploys NO_SIGNAL (no deploy ledger wired up — the bug is a leak, not a regression)

Top hypothesis (87%):
  Redis connection-pool exhaustion in chaos-app
  Backed by: logs (top message is ConnectionError), metrics (error_rate spike
  correlates with chaos_redis_connections climb past 50).
  Why not alternative: not a deploy regression (no deploy events in window);
  not a downstream service issue (Redis itself reachable from other services).

Remediation (LOW risk):
  $ curl -X POST http://chaos-app:8000/admin/reset
    why: clears the leaked connection counter so the pool re-initialises
    expected: error_rate returns to baseline within 30s
    reversal: re-run the load generator to reproduce
```

(Exact wording varies — these are the structural pieces an LLM-refined run
produces, and the structure is guaranteed by the Pydantic schemas.)

---

## Trying it without the SRE Agent dashboard

If you just want to see Prometheus and Loki working, the stack stands alone:

```bash
docker compose -f demo-stack/docker-compose.yml up -d
./demo-stack/scripts/generate-load.sh 80

# Visit Grafana — both datasources pre-wired
open http://localhost:3000

# Or query directly
curl 'http://localhost:9090/api/v1/query?query=chaos_redis_connections'
curl 'http://localhost:3100/loki/api/v1/query?query={service="chaos-app",level="error"}'
```

---

## Notes for the curious

* The chaos-app ships logs to Loki via the push API directly. In real
  production you'd use promtail or Docker's loki log driver — this short
  cut keeps the demo to four containers.
* `oss` provider mode = `PrometheusProvider` for metrics + `LokiProvider`
  for logs, composed via `CompositeProvider`. Traces and deploys remain
  `NO_SIGNAL` — the hypothesis generator weighs that correctly ("not a
  regression in this window").
* Want to add Jaeger/Tempo for traces? Implement `fetch_traces` for a new
  provider and plug it into the composite in `providers/__init__.py`.
* Want to add real deploy detection? Have your CI emit a webhook to
  `/api/alerts/webhook`-style endpoint that writes deploy events to a
  small SQLite file, then implement `fetch_deploys` against that file.
