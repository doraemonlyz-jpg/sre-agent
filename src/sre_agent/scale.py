"""
Phase E — production-scale mocking.

The full production answer (Kafka → Temporal → tiered model routing
across GPU pools) is in `README.md` under "Phase E roadmap". This file
implements the *shape* of those decisions inside the existing demo so
they're testable, demoable, and visible in the dashboard:

  * **Bounded worker pool** — `ThreadPoolExecutor(max_workers=SRE_MAX_CONCURRENT)`.
    Submissions beyond the pool queue up. This is how a webhook burst
    (1000 alerts when a hub service dies) gets absorbed in prod, just
    with Kafka/Temporal instead of an in-process queue.

  * **Tier classifier** — `classify_tier()` decides whether an incident
    is `rule` (no LLM at all), `cheap` (local Llama-style), or
    `premium` (GPT-4o-class). Today the routing is cosmetic — the
    actual LLM call still uses whatever `SRE_LLM_*` envvars say. The
    *visible decision* in the UI tells the prod-scale story: "what %
    of incidents would have hit the expensive model?".

  * **Counters** — `Counters` is a thread-safe snapshot of queue depth,
    completion rate, tier breakdown, and LLM call rate. Surfaced via
    `/api/scale/stats`.

Everything here is in-process and threadsafe. Replacing with Kafka +
Temporal is a swap of two functions (`submit_job`, `record_completion`),
not a rewrite.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Literal

# ──────────────────────────────────────────────────────────────────────────
# Tier classifier
# ──────────────────────────────────────────────────────────────────────────

Tier = Literal["rule", "cheap", "premium"]

TIER_DESCRIPTIONS: dict[Tier, str] = {
    "rule": "rule-based, no LLM (NO_SIGNAL / synthetic / cached)",
    "cheap": "local small model (e.g. Llama-3 70B, qwen2.5-coder)",
    "premium": "premium model (GPT-4o / Claude 3.5 Sonnet)",
}


def classify_tier(
    *,
    severity: str | None,
    description: str | None,
    has_strong_signal: bool | None = None,
    runbook_matched: bool | None = None,
    scenario_id: str | None = None,
) -> Tier:
    """
    Pick a model tier for this incident.

    The actual routing matrix in prod would consider:

      * Severity            (SEV-1 → bias premium)
      * Runbook match score (>0.7 → cheap can cite verbatim → skip premium)
      * Caller cost budget  (per-team monthly quota)
      * Past incident dedup (same alert in last 5min → rule, just point at prior)
      * Time of day         (off-hours, no oncall → premium worth the cost)

    For the demo we use a compact set of heuristics that produces a visible
    mix of tiers across the seeded scenarios.
    """
    desc = (description or "").lower()
    sev = (severity or "SEV-3").upper()

    # Tier-0: rule-based. No LLM at all.
    #   Synthetic / test traffic, obvious false-positives, and any case where
    #   the runbook gave us a direct hit AND severity is low.
    if "test" in desc or "synthetic" in desc or "smoke" in desc:
        return "rule"
    if scenario_id == "false-positive":
        return "rule"
    if has_strong_signal is False and runbook_matched is False:
        # No live evidence + no runbook match → there's nothing for an LLM
        # to reason over. Skip it.
        return "rule"

    # Tier-2: premium. SEV-1 always; SEV-2 when ambiguous (no runbook match
    # and weak signal mix).
    if sev in {"SEV-1", "P1", "CRITICAL"}:
        return "premium"
    if sev in {"SEV-2", "P2", "HIGH"} and runbook_matched is False:
        return "premium"

    # Tier-1: cheap local model — the default for everything else. In prod
    # this is where the volume lives: routine incidents with a runbook hit
    # that a small model can summarize confidently.
    return "cheap"


# ──────────────────────────────────────────────────────────────────────────
# Counters (the live stats surfaced via /api/scale/stats)
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class Counters:
    """Thread-safe rolling counters for the scale strip in the UI."""

    # NOTE: we use an RLock so `snapshot()` can call helper methods that
    # also need the lock without deadlocking. A plain threading.Lock would
    # self-deadlock the moment `snapshot()` calls `llm_calls_last_60s()`.
    _lock: threading.RLock = field(default_factory=threading.RLock)
    submitted_total: int = 0
    started_total: int = 0
    completed_total: int = 0
    by_tier_submitted: dict[str, int] = field(default_factory=lambda: {"rule": 0, "cheap": 0, "premium": 0})
    by_tier_completed: dict[str, int] = field(default_factory=lambda: {"rule": 0, "cheap": 0, "premium": 0})
    llm_calls_total: int = 0
    # Rolling window of timestamps for last 60s LLM call rate.
    _llm_window: deque = field(default_factory=lambda: deque(maxlen=10_000))

    def record_submit(self, tier: Tier) -> None:
        with self._lock:
            self.submitted_total += 1
            self.by_tier_submitted[tier] = self.by_tier_submitted.get(tier, 0) + 1

    def record_start(self) -> None:
        with self._lock:
            self.started_total += 1

    def record_complete(self, tier: Tier) -> None:
        with self._lock:
            self.completed_total += 1
            self.by_tier_completed[tier] = self.by_tier_completed.get(tier, 0) + 1

    def record_llm_call(self) -> None:
        now = time.time()
        with self._lock:
            self.llm_calls_total += 1
            self._llm_window.append(now)

    def llm_calls_last_60s(self) -> int:
        """Trim the rolling window and return the count of calls in the last 60s."""
        cutoff = time.time() - 60.0
        with self._lock:
            while self._llm_window and self._llm_window[0] < cutoff:
                self._llm_window.popleft()
            return len(self._llm_window)

    def snapshot(self) -> dict[str, Any]:
        """Return a UI-friendly stats dict."""
        with self._lock:
            queued = max(0, self.submitted_total - self.started_total)
            active = max(0, self.started_total - self.completed_total)
            return {
                "submitted_total": self.submitted_total,
                "started_total": self.started_total,
                "completed_total": self.completed_total,
                "queued": queued,
                "active": active,
                "by_tier_submitted": dict(self.by_tier_submitted),
                "by_tier_completed": dict(self.by_tier_completed),
                "llm_calls_total": self.llm_calls_total,
                "llm_calls_per_min": self.llm_calls_last_60s(),
            }

    def reset(self) -> None:
        """Test hook."""
        with self._lock:
            self.submitted_total = 0
            self.started_total = 0
            self.completed_total = 0
            self.by_tier_submitted = {"rule": 0, "cheap": 0, "premium": 0}
            self.by_tier_completed = {"rule": 0, "cheap": 0, "premium": 0}
            self.llm_calls_total = 0
            self._llm_window.clear()


# Process-wide singleton.
COUNTERS = Counters()


# ──────────────────────────────────────────────────────────────────────────
# Bounded worker pool
# ──────────────────────────────────────────────────────────────────────────


def _max_concurrent() -> int:
    raw = os.environ.get("SRE_MAX_CONCURRENT_INVESTIGATIONS")
    if not raw:
        raw = os.environ.get("SRE_MAX_CONCURRENT", "4")
    try:
        return max(1, int(raw))
    except ValueError:
        return 4


# We construct the executor lazily so tests can monkeypatch
# SRE_MAX_CONCURRENT before submit_job is first called.
_EXECUTOR: ThreadPoolExecutor | None = None
_EXECUTOR_LOCK = threading.Lock()


def get_executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is not None:
        return _EXECUTOR
    with _EXECUTOR_LOCK:
        if _EXECUTOR is None:
            _EXECUTOR = ThreadPoolExecutor(
                max_workers=_max_concurrent(),
                thread_name_prefix="sre-worker",
            )
    return _EXECUTOR


def reset_executor() -> None:
    """Test hook — drop the executor so the next get_executor() rebuilds it
    from the current env. The old executor is shut down without waiting."""
    global _EXECUTOR
    with _EXECUTOR_LOCK:
        if _EXECUTOR is not None:
            _EXECUTOR.shutdown(wait=False, cancel_futures=True)
            _EXECUTOR = None


def submit_job(
    target: Callable[..., Any],
    *args: Any,
    tier: Tier = "cheap",
    **kwargs: Any,
) -> Future:
    """
    Submit a job to the bounded pool. The first `max_workers` submissions
    run immediately; subsequent ones queue up. This is the in-process
    mock of "Kafka → Temporal worker pool" in production.

    `tier` is recorded in the counters so the dashboard can show the
    rule/cheap/premium breakdown.
    """
    COUNTERS.record_submit(tier)
    executor = get_executor()

    def _wrapped(*a: Any, **kw: Any) -> Any:
        COUNTERS.record_start()
        try:
            return target(*a, **kw)
        finally:
            COUNTERS.record_complete(tier)

    return executor.submit(_wrapped, *args, **kwargs)
