"""
sre_agent.concurrency -- thread-safe LLM fan-out helper (G2).

Why this exists
---------------
LangGraph already parallelises the 5 worker nodes (PM, log, metrics,
trace, deploys, runbook). What it does NOT parallelise is multiple LLM
calls *within a single node* -- e.g. running an N-of-K self-consistency
vote on the hypothesis generator.

Why not asyncio?
----------------
LangGraph's sync nodes run on a thread pool internally; the LLM clients
(`ChatOllama`, `ChatOpenAI`, etc.) do not all expose ergonomic `ainvoke`
for our `with_structured_output` flow today. Threads work, are
LangGraph-native, and don't require flipping the whole graph to async.
The bottleneck is the model server's queue depth, NOT Python's GIL --
the GIL releases on socket I/O, which is exactly what an LLM call is.

What you get
------------
* `concurrent_llm_calls(funcs, max_workers=k)`:
    Runs up to `k` callables in parallel; preserves ContextVars so the
    `harness` recorder still attributes each call to the right
    `incident_id` and `agent`.
* `ensemble_pick_best(results, key)`:
    Picks the highest-`key` result from a list (typically `confidence`).
* `ensemble_agreement(results, key)`:
    Computes the agreement ratio: how many ensemble members produced
    the same top answer (by `key` value, with a tolerance bucket).
    Surfaces in Prometheus as `sre_ensemble_agreement`.

Self-metrics
------------
Each `concurrent_llm_calls` invocation increments
`sre_ensemble_runs_total{agent,k,outcome}` and observes
`sre_ensemble_latency_seconds`.
"""

from __future__ import annotations

import contextvars
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger("sre_agent.concurrency")


@dataclass
class CallOutcome:
    """Wrap an ensemble member's result so callers can tell which
    succeeded vs. errored without losing the exception. `value` is
    intentionally `Any` -- the helper is generic across LLM result
    types and we don't want to thread typevars through the dataclass."""
    ok: bool
    value: Any
    error: str | None
    latency_s: float


# ──────────────────────────────────────────────────────────────────────────
# Concurrent fan-out
# ──────────────────────────────────────────────────────────────────────────


def concurrent_llm_calls(
    funcs: list[Callable[[], Any]],
    *,
    agent: str = "unknown",
    max_workers: int | None = None,
    timeout_s: float | None = 120.0,
) -> list[CallOutcome]:
    """
    Run `funcs` concurrently and return outcomes in the SAME ORDER as
    input. Failures (exceptions, timeout) are caught -- the caller sees
    `CallOutcome(ok=False, ...)` rather than a raise.

    ContextVars (used by the harness) are explicitly copied into worker
    threads so the call records still know "this LLM call belongs to
    incident X, agent Y".

    `agent` is the LangGraph node name (only used as a metric label).
    """
    if not funcs:
        return []

    n = len(funcs)
    workers = max(1, min(max_workers or n, n))
    # IMPORTANT: `Context.run()` can be entered ONCE; entering the
    # same Context from two threads raises "cannot enter context". So
    # take a fresh per-task snapshot of the parent's ContextVars and
    # let each worker thread enter its own copy.
    per_task_ctx = [contextvars.copy_context() for _ in range(n)]
    outcomes: list[CallOutcome] = [
        CallOutcome(ok=False, value=None, error="not run", latency_s=0.0)
        for _ in range(n)
    ]

    def _run_in_ctx(idx: int, fn: Callable[[], Any]) -> CallOutcome:
        t0 = time.perf_counter()
        try:
            value = per_task_ctx[idx].run(fn)
            return CallOutcome(
                ok=True, value=value, error=None,
                latency_s=time.perf_counter() - t0,
            )
        except Exception as e:
            return CallOutcome(
                ok=False, value=None, error=f"{type(e).__name__}: {str(e)[:240]}",
                latency_s=time.perf_counter() - t0,
            )

    overall_t0 = time.perf_counter()
    try:
        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix=f"sre-ens-{agent}",
        ) as pool:
            future_to_idx = {
                pool.submit(_run_in_ctx, i, fn): i for i, fn in enumerate(funcs)
            }
            for fut in as_completed(future_to_idx, timeout=timeout_s):
                idx = future_to_idx[fut]
                try:
                    outcomes[idx] = fut.result()
                except Exception as e:
                    outcomes[idx] = CallOutcome(
                        ok=False, value=None,
                        error=f"future-{type(e).__name__}: {str(e)[:200]}",
                        latency_s=0.0,
                    )
    except TimeoutError:
        # Some futures may not have completed -- they keep the placeholder
        log.warning("concurrent_llm_calls timeout after %.1fs", timeout_s or 0)

    overall_latency = time.perf_counter() - overall_t0
    n_ok = sum(1 for o in outcomes if o.ok)
    outcome = "ok" if n_ok == n else ("partial" if n_ok > 0 else "all_failed")

    try:
        from sre_agent.metrics import (
            ENSEMBLE_LATENCY,
            ENSEMBLE_RUNS_TOTAL,
        )
        ENSEMBLE_RUNS_TOTAL.labels(agent=agent, k=str(n), outcome=outcome).inc()
        ENSEMBLE_LATENCY.labels(agent=agent).observe(overall_latency)
    except Exception:
        pass

    return outcomes


# ──────────────────────────────────────────────────────────────────────────
# Pickers
# ──────────────────────────────────────────────────────────────────────────


def ensemble_pick_best(
    outcomes: list[CallOutcome],
    *,
    score_fn: Callable[[Any], float],
) -> tuple[Any, dict[str, Any]]:
    """
    From a list of ensemble outcomes, return the value with the
    highest score (typically `confidence`), plus diagnostic info.

    Returns `(best_value, info)` where `info` includes:
      * `n_total` -- ensemble size
      * `n_ok`    -- successes
      * `scores`  -- per-member scores (None for failures)
      * `winner_score`
      * `winner_index`
    """
    n_total = len(outcomes)
    successes = [(i, o.value) for i, o in enumerate(outcomes) if o.ok and o.value is not None]
    scores: list[float | None] = [None] * n_total
    for i, v in successes:
        try:
            scores[i] = float(score_fn(v))
        except Exception:
            scores[i] = None

    best_idx = -1
    best_score = float("-inf")
    best_value: Any = None
    for i, v in successes:
        s = scores[i]
        if s is not None and s > best_score:
            best_score, best_idx, best_value = s, i, v

    return best_value, {
        "n_total": n_total,
        "n_ok": len(successes),
        "scores": scores,
        "winner_score": (best_score if best_idx >= 0 else None),
        "winner_index": (best_idx if best_idx >= 0 else None),
    }


def ensemble_agreement(
    outcomes: list[CallOutcome],
    *,
    bucket_fn: Callable[[Any], str],
) -> float:
    """
    Compute the agreement ratio: of the successful ensemble members,
    what fraction produced the same `bucket_fn(value)` as the modal
    bucket? Returns 0.0 if no successes; 1.0 if all agree.

    Use a bucket_fn like `lambda h: h.title.lower()[:40]` to count
    "essentially the same root cause".
    """
    buckets: dict[str, int] = {}
    n_ok = 0
    for o in outcomes:
        if not o.ok or o.value is None:
            continue
        n_ok += 1
        try:
            b = bucket_fn(o.value)
        except Exception:
            b = "_error_bucket_"
        buckets[b] = buckets.get(b, 0) + 1
    if n_ok == 0:
        return 0.0
    return max(buckets.values()) / n_ok
