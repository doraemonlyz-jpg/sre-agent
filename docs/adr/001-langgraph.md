# ADR-001: LangGraph as the orchestrator

- **Status:** Accepted
- **Date:** 2026-04-02
- **Deciders:** core team

## Context

The agent has six investigators (logs, metrics, traces, deploys,
runbooks, hypothesis, remediation) plus an incident PM that fans out
work and a finalizer. We need to:

1. Run the four telemetry workers in parallel (latency budget is 10
   minutes wall-clock for SEV-2; serial would burn 5+ minutes alone).
2. Resume from a checkpoint when a worker dies mid-run (Flask process
   restart, OOM, etc.) without re-paying the LLM cost of completed
   nodes.
3. Stream per-node events to the dashboard live, not after the whole
   pipeline finishes.
4. Keep the agent code itself dumb — each node is a pure
   `state -> partial_state` function. Coordination lives elsewhere.

## Decision

Use **LangGraph** with `StateGraph`, sync `add_node`, and a
`SqliteSaver` (dev) / `PostgresSaver` (prod) checkpointer.

Concretely, `src/sre_agent/graph.py:build_graph` defines a static DAG:

```text
START
  → incident_pm
    → log_detective ┐
    → metrics_analyst ├ (parallel fan-out)
    → trace_reader  │
    → deploy_historian │
    → runbook_consultant ┘
    → hypothesis_generator (fan-in)
      → remediation_suggester
        → finalize
          → END
```

LangGraph's reducer (`operator.add` on the `events` field) merges the
five branches' append-only event lists deterministically.

## Considered

- **Plain `concurrent.futures` + a hand-rolled state dict.** Cheaper
  to start, but we'd have to reinvent: checkpointing, resumable
  streaming, the reducer pattern for parallel writers, and the
  conditional-edge semantics we use in `incident_pm` to short-circuit
  on a NO_SIGNAL alert. The complexity savings vanish by the second
  feature.
- **CrewAI / autogen.** More opinionated about role-play / multi-turn
  chat. Less natural for a static DAG with structured Pydantic I/O.
  We'd be fighting the framework.
- **Temporal / Airflow.** Right answer for week-long workflows or jobs
  measured in hours; massive overkill for a 10-minute incident
  pipeline. Operational cost dwarfs the win.

## Consequences

- **Good:** every new agent is one `add_node` + one persona file +
  three lines in `graph.py`. The dashboard's live-event stream is
  `for ev in graph.stream(...)` — no extra plumbing.
- **Good:** crashing in the middle of an incident is recoverable —
  the SQLite/Postgres checkpoint rehydrates the state.
- **Bad:** LangGraph is young (1.x as of writing) and has had two
  breaking releases. We pin it tightly in `pyproject.toml` and have
  an integration test (`tests/test_graph_integration.py`) so upgrades
  surface fast.
- **Bad:** sync nodes only. To do an in-node ensemble we use a
  thread-pool helper (see [ADR-007](./007-ensemble-via-threads.md))
  rather than rewriting to `astream`.
