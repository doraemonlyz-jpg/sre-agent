# ADR-002: SQLite for checkpoints in dev, Postgres in prod

- **Status:** Accepted
- **Date:** 2026-04-04

## Context

LangGraph requires a checkpointer for resumability. Two production-ready
options ship with `langgraph`: SQLite and Postgres. We have to pick a
default that:

1. Works on a laptop with zero setup (interview demos, contributor
   onboarding, CI).
2. Survives the dashboard process restarting mid-incident in prod.
3. Doesn't bottleneck on the checkpoint write path -- LangGraph
   serialises one row per node-step, which can hit ~50 writes per
   incident.

## Decision

- **Default:** SQLite at `./.state/checkpoints.db`. Long-lived
  connection with `check_same_thread=False` (Flask spawns worker
  threads).
- **Production toggle:** `SRE_CHECKPOINTER=postgres` switches to
  `PostgresSaver.from_conn_string($DATABASE_URL)` and runs `setup()`
  on boot.

`src/sre_agent/graph.py:_default_checkpointer` does the env switch
in one place; nothing else in the codebase knows what backend is in
use.

## Considered

- **Default to Postgres everywhere.** Rejected because a fresh
  `git clone && pytest` would require docker-compose. Friction kills
  contributors faster than any other reason.
- **Redis Streams as the checkpointer.** Tempting (low write latency,
  TTLs for free) but LangGraph doesn't ship a Redis saver and rolling
  our own is risk for no clear win.
- **In-memory MemorySaver.** Used in some unit tests; not viable as
  a production default because a Flask restart loses every in-flight
  incident.

## Consequences

- **Good:** zero-config dev story. SQLite is also fast enough for
  ~100 concurrent incidents on a laptop -- well above demo / interview
  scale.
- **Good:** prod path is a one-env-var flip; no code change needed.
- **Bad:** SQLite uses a file lock. Two dashboard processes writing
  to the same `.state/` will fight. We document this in
  `docs/ops-runbook.md` and recommend Postgres for any deployment
  with > 1 replica.
- **Bad:** `LANGGRAPH_STRICT_MSGPACK=true` (an upcoming default)
  will require us to register our Pydantic schemas with LangGraph's
  serde. Tracked as a known follow-up in the deprecation warnings.
