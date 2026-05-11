# Cascading failures — how to find the real root cause

The first service to alert is rarely the one that actually broke. This
playbook explains how to walk the dependency graph backwards to the
actual root cause.

## Detection pattern

> tags: cascade, downstream, trace, root-cause

When you suspect cascade rather than local failure:

- The alerting service's **own** metrics (CPU, GC, memory) look fine
- Trace analysis shows the hot span is a **call OUT** of the service
  (an HTTP client, a DB query, a Redis op), not internal work
- The error message mentions a downstream identifier (a hostname, a
  service mesh peer, a database connection string)
- Multiple services that share the same downstream all alert within
  seconds of each other

## Investigation steps

> tags: cascade, runbook

1. **Identify the actual sick service.** Look at the trace's
   downstream_suspect field. If it points elsewhere, you have your
   root cause.
2. **Open a parallel investigation** on the sick service — don't keep
   debugging the canary.
3. **Protect yourself** in the meantime: enable circuit breakers on the
   client side so your service fails fast instead of holding connections
   open waiting for a dead downstream.
4. **Communicate**: notify the owning team of the downstream service in
   their oncall channel. Cascading failures need parallel response, not
   serial.

## Anti-patterns

> tags: anti-pattern, dont-do-this

- **Restarting your own service** when the downstream is the problem —
  it'll just immediately re-cascade.
- **Rolling back a recent deploy** when the deploy is unrelated to the
  cascade. Time-correlation is suggestive, not causal.
- **Adding retries** to the downstream call — this amplifies load on
  the already-sick downstream and makes things worse.
