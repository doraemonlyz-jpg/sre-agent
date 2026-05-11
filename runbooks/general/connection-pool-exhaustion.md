# Connection pool exhaustion — general pattern

Cross-cutting pattern that applies to any service with a pooled
client (Redis, Postgres, MySQL, HTTP keepalive, gRPC channels, etc.).

## Telemetry fingerprint

> tags: connection-pool, regression, capacity

Three signals usually co-occur — at least two of them must be present
to assert "pool exhaustion" rather than "downstream down":

1. **Logs**: errors mentioning `connection refused`, `pool exhausted`,
   `acquire timeout`, `max connections reached`, `too many open files`,
   or driver-specific equivalents (`OperationalError: FATAL: too many
   clients` for Postgres; `MaxRetryError` for HTTP pools).
2. **Metrics**: a custom or driver-exported gauge of "active
   connections" or "pool in-use" climbing monotonically over the window.
   If the gauge stays flat, this isn't pool exhaustion.
3. **Latency**: p99 jumps before the error rate does. Connections take
   longer to acquire, then start timing out.

## Distinguishing from "downstream service is dead"

> tags: differential-diagnosis

If the *downstream* (Redis, Postgres) is dead, you'll see:

- Errors on **multiple** services that share the downstream
- Connection failures even from a fresh process / new pool
- Downstream's own monitoring (Redis INFO, Postgres pg_stat_activity)
  showing distress

If only the pool is exhausted:

- Errors localized to **one** service
- A restart of that service immediately fixes the symptom
- Downstream looks healthy from anything *not* sharing the pool

## Universal mitigation

1. **Restart the affected pods**. This drops the leaked connections.
   Risk: drops in-flight requests. For most services, acceptable for <2s.
2. **If a deploy preceded the alert**: roll back. Pool leaks are almost
   always introduced by code changes that move connection lifecycle.
3. **As a last resort**: raise the pool size. This buys time but doesn't
   fix the underlying leak.

**NEVER** silently catch and discard `ConnectionError` in a retry loop
without exponential backoff — that just amplifies the leak.
