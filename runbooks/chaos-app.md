# chaos-app runbook

The demo target service used by `demo-stack/`. Endpoints under
`http://chaos-app:8000` exhibit deliberate failure modes — each section
below documents one of them.

## Redis connection pool exhaustion

> service: chaos-app
> tags: redis, connection-pool, leak, error_rate

**Symptoms**

- `chaos_redis_connections` gauge climbing monotonically past ~50
- `error_rate` for `/redis-leak` jumps from <0.1/s to >5/s within seconds
- Logs full of `redis.exceptions.ConnectionError: Connection refused — pool exhausted`
- `p99` latency on `/redis-leak` jumps from <50ms baseline to >2s

**Likely cause**

The leak counter in `app.py` has exceeded `REDIS_LEAK_LIMIT` (default 50).
This is the deliberate bug in `redis_leak()` — every call increments the
pool counter without ever releasing. Once we cross the limit, every
subsequent call returns 500.

**Mitigation** (LOW risk — pure in-memory state, no real Redis touched)

1. `curl -X POST http://chaos-app:8000/admin/reset` — clears the leak counter
2. Verify recovery: `curl http://chaos-app:8000/healthy` should return 200
3. Watch `chaos_redis_connections` drop to 0 in Grafana within 5 seconds

**Prevention**

The "fix" would be to call `conn.close()` (or use a context manager) in
`redis_leak()`. Since this is the demo's signature bug, we keep it broken
on purpose.

**Related**

- Demo recipe: `demo-stack/README.md`
- Load generator: `demo-stack/scripts/generate-load.sh`

## Slow endpoint latency

> service: chaos-app
> tags: latency, slow

**Symptoms**

- `latency_p99` on `/slow` reports 100-2000ms randomly
- `req_rate` and `error_rate` look normal
- No error logs

**Likely cause**

`/slow` deliberately sleeps a random 100-2000ms before responding. It's
ambient noise to make the demo metrics more interesting, not a real
failure mode.

**Mitigation**

None needed. If `/slow` latency is the *only* anomaly, this is a false
positive — the alert threshold for that endpoint should be raised, or
`/slow` excluded from the alert's query.

## Random 5xx noise

> service: chaos-app
> tags: error_rate, noise

**Symptoms**

- Occasional 500s from `/crash` at a steady ~5% rate
- No correlation with deploys, traffic spikes, or other endpoints

**Likely cause**

`/crash` returns 500 with probability 0.05. It exists to give the
metrics_analyst a nonzero baseline error rate so spike detection has
something to compare against.

**Mitigation**

If `error_rate` on `/crash` is the *only* signal, it's noise — not an
incident.
