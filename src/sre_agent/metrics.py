"""
sre_agent.metrics -- Prometheus instrumentation (B1).

Why a single file
-----------------
Production observability lives at three layers:

  1. **Structured logs** (structlog) -- what HAPPENED on this request.
  2. **Distributed traces** (Langfuse / OTLP -- already wired in
     `observability.py`) -- what an LLM call DID and how long it took.
  3. **Metrics** (this file) -- aggregate signal: QPS, p95/p99
     latencies, error rates, queue depth, calibrator drift.

A real on-call uses (3) for paging and dashboards, (1) for triage, (2)
for deep-dive. Each is necessary; none replaces the others.

Why one file
------------
All counter / histogram / gauge declarations live here so that:
  * `from sre_agent.metrics import INCIDENT_LATENCY` is the only import
    needed at the call site (no scattered "where is this metric defined?").
  * Tests can `import sre_agent.metrics as M; M.REGISTRY.collect()` to
    assert against the live snapshot.
  * Renames touch one file.

What we expose
--------------
The full set is intentionally small -- a dashboard with 200 metrics is
unusable. Coverage:

  * `sre_incidents_total{result}`              counter
  * `sre_incident_duration_seconds`            histogram (p50/p95/p99)
  * `sre_llm_calls_total{agent,model,status}`  counter
  * `sre_llm_latency_seconds{agent,model}`     histogram
  * `sre_llm_tokens_total{agent,direction}`    counter
  * `sre_llm_fallbacks_total{agent,from_tier,to_tier,reason}`  counter (B4)
  * `sre_cache_events_total{kind}`             counter (hit / miss / store)
  * `sre_feedback_total{verdict}`              counter
  * `sre_rate_limit_drops_total{scope}`        counter (L5)
  * `sre_calibrator_ece` / `sre_calibrator_brier`   gauge
  * `sre_runbook_search_total{backend,hit}`    counter
  * `sre_runbook_search_latency_seconds{backend}`   histogram
  * `sre_active_incidents`                     gauge
  * `sre_build_info{version,git_sha,checkpointer}` gauge (constant 1)

All names follow Prometheus naming conventions: `_total` suffix for
counters, base-unit (`seconds`, `bytes`) suffix on histograms, no units
on gauges that are dimensionless. Labels are LOW-cardinality on purpose
-- never put `incident_id` or `user_id` on a metric label.

Boot-safety
-----------
The module never raises on import. If `prometheus_client` is somehow
unavailable in the runtime, we fall back to a stub Registry that
silently swallows all `inc()` / `observe()` / `set()` calls. The
dashboard's `/metrics` endpoint then returns an explanatory text body
with HTTP 200 -- a missing scrape target is worse than a degraded one.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator

log = logging.getLogger("sre_agent.metrics")


# ──────────────────────────────────────────────────────────────────────────
# Optional dependency -- never fail import
# ──────────────────────────────────────────────────────────────────────────

try:
    from prometheus_client import (  # type: ignore[import-not-found]
        CONTENT_TYPE_LATEST,
        REGISTRY,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    _PROM_OK = True
except Exception as e:  # pragma: no cover -- only hit if pip install fails
    log.warning("prometheus_client not available: %s", e)
    _PROM_OK = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    REGISTRY = None  # type: ignore[assignment]

    # Stubs so the rest of the module loads even without prometheus_client.
    class _Stub:  # noqa: D401
        """Silent no-op replacement for Counter / Gauge / Histogram."""

        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        def labels(self, *_a: Any, **_k: Any) -> "_Stub":
            return self

        def inc(self, *_a: Any, **_k: Any) -> None:
            pass

        def dec(self, *_a: Any, **_k: Any) -> None:
            pass

        def set(self, *_a: Any, **_k: Any) -> None:
            pass

        def observe(self, *_a: Any, **_k: Any) -> None:
            pass

    Counter = _Stub  # type: ignore[assignment,misc]
    Gauge = _Stub  # type: ignore[assignment,misc]
    Histogram = _Stub  # type: ignore[assignment,misc]
    CollectorRegistry = _Stub  # type: ignore[assignment,misc]

    def generate_latest(*_a: Any, **_k: Any) -> bytes:  # type: ignore[misc]
        return (
            b"# prometheus_client is not installed in this environment.\n"
            b"# Install with: pip install prometheus-client\n"
        )


# ──────────────────────────────────────────────────────────────────────────
# Metric declarations
#
# Histograms use SRE-relevant buckets:
#   - LLM latency: 100ms to 60s (covers cache hits, cheap, premium, timeouts)
#   - Incident latency: 1s to 300s (target diagnosis <90s, alert at 300s)
#   - Runbook search: 1ms to 1s (in-memory ranking, should always be fast)
# ──────────────────────────────────────────────────────────────────────────

INCIDENTS_TOTAL = Counter(
    "sre_incidents_total",
    "Number of incidents seen by the agent, by terminal phase.",
    ["result"],  # diagnosed | no_signal | timeout | error
)

INCIDENT_DURATION = Histogram(
    "sre_incident_duration_seconds",
    "Wall time from alert fire to terminal phase, in seconds.",
    ["result"],
    buckets=(1, 5, 15, 30, 60, 90, 120, 180, 300, 600, 1800),
)

LLM_CALLS_TOTAL = Counter(
    "sre_llm_calls_total",
    "LLM invocations by agent, model, and outcome.",
    ["agent", "model", "status"],  # status: ok | error | cache_hit
)

LLM_LATENCY = Histogram(
    "sre_llm_latency_seconds",
    "LLM call wall-time, in seconds.",
    ["agent", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 40.0, 60.0),
)

LLM_TOKENS_TOTAL = Counter(
    "sre_llm_tokens_total",
    "Total tokens used, by agent and direction.",
    ["agent", "direction"],  # direction: input | output
)

LLM_FALLBACKS_TOTAL = Counter(
    "sre_llm_fallbacks_total",
    "B4 fallback transitions, by agent and the (from, to) tier pair.",
    ["agent", "from_tier", "to_tier", "reason"],  # reason: timeout | error | rate_limit
)

CACHE_EVENTS_TOTAL = Counter(
    "sre_cache_events_total",
    "Response-cache events.",
    ["kind"],  # hit | miss | store | evict
)

FEEDBACK_TOTAL = Counter(
    "sre_feedback_total",
    "Oncall verdicts written to the feedback store.",
    ["verdict"],  # thumbs_up | thumbs_down | correct | incorrect
)

RATE_LIMIT_DROPS_TOTAL = Counter(
    "sre_rate_limit_drops_total",
    "Requests rejected by the L5 token-bucket rate limiter.",
    ["scope"],
)

# Calibrator health (B3). Gauges -- set on calibrator load and on
# every successful re-fit. ECE / Brier on the training set are
# point-in-time fit quality; a watchdog alert on
# `sre_calibrator_ece > 0.1` catches drift before it hits oncall.
CALIBRATOR_ECE = Gauge(
    "sre_calibrator_ece",
    "Expected Calibration Error of the currently-loaded calibrator (training set).",
)
CALIBRATOR_BRIER = Gauge(
    "sre_calibrator_brier",
    "Brier score of the currently-loaded calibrator (training set).",
)
CALIBRATOR_N_TRAIN = Gauge(
    "sre_calibrator_n_train",
    "Number of (confidence, outcome) pairs the active calibrator was fit on.",
)

# Runbook RAG (C1).
RUNBOOK_SEARCH_TOTAL = Counter(
    "sre_runbook_search_total",
    "Runbook RAG searches by backend and hit/miss status.",
    ["backend", "hit"],  # hit: "true" | "false"
)
RUNBOOK_SEARCH_LATENCY = Histogram(
    "sre_runbook_search_latency_seconds",
    "Time spent ranking runbook hits.",
    ["backend"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

ACTIVE_INCIDENTS = Gauge(
    "sre_active_incidents",
    "Currently-investigating incidents (live count).",
)

BUILD_INFO = Gauge(
    "sre_build_info",
    "Build / runtime info as labels (value is always 1).",
    ["version", "checkpointer", "llm_provider"],
)


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────


@contextmanager
def time_llm_call(agent: str, model: str) -> Iterator[None]:
    """Context manager that times an LLM call into LLM_LATENCY."""
    started = time.perf_counter()
    try:
        yield
    finally:
        LLM_LATENCY.labels(agent=agent, model=model).observe(
            time.perf_counter() - started
        )


@contextmanager
def time_runbook_search(backend: str) -> Iterator[None]:
    """Context manager that times a runbook RAG search."""
    started = time.perf_counter()
    try:
        yield
    finally:
        RUNBOOK_SEARCH_LATENCY.labels(backend=backend).observe(
            time.perf_counter() - started
        )


def record_llm_call(
    *,
    agent: str,
    model: str,
    status: str,
    latency_seconds: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> None:
    """One-call helper -- increments the counter + optionally records
    latency + tokens. Convenience for the harness callback to call once
    per LLM completion."""
    LLM_CALLS_TOTAL.labels(agent=agent, model=model, status=status).inc()
    if latency_seconds is not None:
        LLM_LATENCY.labels(agent=agent, model=model).observe(latency_seconds)
    if input_tokens is not None:
        LLM_TOKENS_TOTAL.labels(agent=agent, direction="input").inc(input_tokens)
    if output_tokens is not None:
        LLM_TOKENS_TOTAL.labels(agent=agent, direction="output").inc(output_tokens)


def record_incident_terminal(*, result: str, duration_seconds: float) -> None:
    """Called when an incident transitions to its terminal phase."""
    INCIDENTS_TOTAL.labels(result=result).inc()
    INCIDENT_DURATION.labels(result=result).observe(duration_seconds)


def record_cache_event(kind: str) -> None:
    CACHE_EVENTS_TOTAL.labels(kind=kind).inc()


def record_feedback(verdict: str) -> None:
    FEEDBACK_TOTAL.labels(verdict=verdict).inc()


def record_rate_limit_drop(scope: str) -> None:
    RATE_LIMIT_DROPS_TOTAL.labels(scope=scope).inc()


def record_fallback(*, agent: str, from_tier: str, to_tier: str, reason: str) -> None:
    LLM_FALLBACKS_TOTAL.labels(
        agent=agent, from_tier=from_tier, to_tier=to_tier, reason=reason,
    ).inc()


def record_runbook_search(*, backend: str, hit: bool) -> None:
    RUNBOOK_SEARCH_TOTAL.labels(backend=backend, hit="true" if hit else "false").inc()


def update_calibrator_health(*, ece: float, brier: float, n_train: int) -> None:
    """Set the calibrator-health gauges. Called on dashboard boot and
    on every successful calibrator re-fit."""
    CALIBRATOR_ECE.set(ece)
    CALIBRATOR_BRIER.set(brier)
    CALIBRATOR_N_TRAIN.set(n_train)


_active_lock = threading.Lock()
_active_count = 0


def incident_started() -> None:
    global _active_count
    with _active_lock:
        _active_count += 1
        ACTIVE_INCIDENTS.set(_active_count)


def incident_ended() -> None:
    global _active_count
    with _active_lock:
        _active_count = max(0, _active_count - 1)
        ACTIVE_INCIDENTS.set(_active_count)


def set_build_info(*, version: str, checkpointer: str, llm_provider: str) -> None:
    BUILD_INFO.labels(
        version=version, checkpointer=checkpointer, llm_provider=llm_provider,
    ).set(1)


# ──────────────────────────────────────────────────────────────────────────
# Render the /metrics body
# ──────────────────────────────────────────────────────────────────────────


def render_latest() -> tuple[bytes, str]:
    """Return (body, content_type) ready to flask.Response back."""
    if not _PROM_OK:
        body = (
            b"# prometheus_client is not installed in this environment.\n"
            b"# Install with: pip install prometheus-client\n"
        )
        return body, CONTENT_TYPE_LATEST
    return generate_latest(), CONTENT_TYPE_LATEST


# ──────────────────────────────────────────────────────────────────────────
# Process-wide one-shot init
# ──────────────────────────────────────────────────────────────────────────


def initialise_from_env() -> None:
    """Set the build-info gauge from current environment.

    Called once from dashboard boot. Safe to call multiple times -- the
    gauge label set is fixed and setting it again is a no-op other than
    label-value churn.
    """
    set_build_info(
        version=os.environ.get("SRE_AGENT_VERSION") or "dev",
        checkpointer=os.environ.get("SRE_CHECKPOINTER") or "sqlite",
        llm_provider=os.environ.get("SRE_LLM_PROVIDER") or "auto",
    )
