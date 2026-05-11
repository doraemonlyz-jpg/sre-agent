# checkout-api runbook

The fictional service used in the mock scenarios (`redis-pool-exhaustion`,
`false-positive`, `downstream-cascade`). These sections mirror the demo
data so the runbook_consultant has something concrete to retrieve when
those scenarios fire.

## Connection pool exhaustion after deploy

> service: checkout-api
> tags: redis, deploy, connection-pool, regression

**Symptoms**

- Recent deploy (within last 30 min) of `checkout-api`
- Spike in `error_rate` to ~50x baseline within 5 min of the deploy
- Logs flooded with `redis.exceptions.ConnectionError`
- `chaos_redis_connections` or equivalent connection-count metric climbing

**Likely cause**

A code change reduced or removed connection releases — possibly a
forgotten `await conn.close()` or a misconfigured `redis.ConnectionPool`
size. Historical analog: 2024-10-12, PR #1234 introduced a `with redis.Redis()`
context that wasn't properly exiting on exception paths.

**Mitigation** (MEDIUM risk — affects live traffic)

1. **Roll back the deploy** (preferred):
   `kubectl rollout undo deploy/checkout-api -n prod`
   Reversal: `kubectl rollout undo deploy/checkout-api -n prod --to-revision=N`
2. If rollback isn't available, restart the pods to release connections:
   `kubectl rollout restart deploy/checkout-api -n prod`
3. Verify within 60s: `kubectl logs ... | grep ConnectionError` should
   stop, and error_rate should return to baseline.

**Prevention**

Required code review check: any new code paths that acquire a Redis
connection must exit via a `try/finally` or `async with`. CI lint rule
proposed in PR #2018.

## False-positive: deploy with no real impact

> service: checkout-api
> tags: false-positive, noise

**Symptoms**

- Alert fires (e.g. on a sensitive p99 threshold)
- Logs show normal error baseline (<5/min)
- Metrics show a brief blip but nothing sustained
- No correlated trace anomalies
- Recent deploy but timing doesn't align with the alert window

**Likely cause**

Either (a) a transient network blip, (b) an over-sensitive alert
threshold, or (c) the deploy genuinely shipped without breaking anything
and the alert tracked a coincidental noise event.

**Mitigation**

1. Do NOT roll back unless evidence accumulates over the next 10 min.
2. Watch the dashboard for 10 min; if metrics stay nominal, mark as
   resolved and tag the incident as "false positive".
3. File a ticket to tune the alert threshold (a 1-minute spike shouldn't
   page; a 5-minute trend should).

**Prevention**

Add hysteresis to the monitor — require N consecutive minutes above
threshold before firing.

## Downstream cascade

> service: checkout-api
> tags: downstream, cascade, payments

**Symptoms**

- `checkout-api` errors correlate with `payments-svc` errors at the
  same minute
- Trace inspector reveals the hot span is a call OUT of `checkout-api`
  into `payments-svc`
- `checkout-api`'s own metrics (CPU, memory, GC) look fine

**Likely cause**

`payments-svc` is the actual sick service; `checkout-api` is just the
canary because it calls payments synchronously and forwards the failure
upstream.

**Mitigation**

1. **Stop investigating checkout-api**. Open a parallel investigation on
   `payments-svc` — that's where the root cause lives.
2. Temporary: enable the payments circuit breaker on checkout-api side
   to fail fast and shed load:
   `kubectl set env deploy/checkout-api PAYMENTS_CIRCUIT_BREAKER=open`
   Reversal: `... PAYMENTS_CIRCUIT_BREAKER=closed`
3. Notify the payments oncall (channel `#oncall-payments`).
