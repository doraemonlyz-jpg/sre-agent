# ADR-007: Ensemble via threads, not asyncio refactor

- **Status:** Accepted
- **Date:** 2026-05-13

## Context

Self-consistency voting (Wang et al., 2022) is a known way to
improve LLM accuracy by running K parallel calls and picking the
most-confident answer. We wanted to add that to `hypothesis_gen`.

The orthodox way to do K parallel LLM calls inside a node is to
make the node `async` and `await asyncio.gather([llm.ainvoke(...)
for _ in range(K)])`. Doing that here means flipping the entire
LangGraph from sync `add_node` / `stream` to async `ainvoke` /
`astream`, plus making Flask handle the async-bridge cleanly.

## Decision

Add `src/sre_agent/concurrency.py:concurrent_llm_calls` -- a
thread-pool helper that:

1. Snapshots the parent thread's `ContextVars` per task (the harness
   relies on them to attribute LLM calls to the right incident /
   agent).
2. Submits up to K callables to a `ThreadPoolExecutor`.
3. Returns ordered `CallOutcome` records so callers see who failed
   without losing the per-member exception.

`hypothesis_generator` reads `SRE_HYPOTHESIS_ENSEMBLE_K` and uses
the helper when K > 1; falls back to the single-call path when K = 1
to skip thread-pool overhead entirely.

## Considered

- **Full async rewrite.** Done correctly this is ~6 nodes + the graph
  build + the Flask handler + every test that touches the graph. The
  bottleneck for our deployments is usually Ollama's queue depth,
  which serialises requests anyway -- async wouldn't actually parallelise
  what matters.
- **Multiprocessing.** Pickling the LLM client and the LangChain
  callbacks across processes is fragile. We don't need true CPU
  parallelism; the GIL releases on socket I/O for LLM calls.
- **Sync loop with `httpx` AsyncClient under the hood.** Half-async
  half-sync code is the worst of both worlds; we'd still owe the
  full LangGraph migration to use it cleanly.

## Consequences

- **Good:** ensemble is opt-in via env. Existing single-call behaviour
  is the default; no graph or Flask changes.
- **Good:** ContextVars-aware -- the harness still attributes calls
  per ensemble member.
- **Good:** the helper is reusable: any future node that wants to
  fan out N LLM calls (e.g. parallel retrieval rerank, parallel
  hypothesis verification) can use it without touching the graph.
- **Bad:** if a model server is single-threaded and serialises
  internally, the wall-clock benefit is small (the K calls queue).
  We measure this in `tests/test_concurrency.py::test_concurrent_runs_actually_overlap`
  and surface `sre_ensemble_latency_seconds` so ops can dashboard
  the actual gain.
- **Bad:** thread-pool overhead is real (~10ms) for the K=2 case;
  the K-gate check (`if k <= 1`) prevents paying it on the default path.
