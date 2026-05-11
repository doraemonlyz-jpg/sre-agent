"""Unit tests for the Phase E production-scale mock."""

from __future__ import annotations

import time

import pytest

from sre_agent.scale import (
    COUNTERS,
    classify_tier,
    get_executor,
    reset_executor,
    submit_job,
)


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch):
    """Each test starts with fresh counters and a fresh executor."""
    COUNTERS.reset()
    reset_executor()
    yield
    COUNTERS.reset()
    reset_executor()


# ──────────────────────────────────────────────────────────────────────────
# Tier classifier
# ──────────────────────────────────────────────────────────────────────────


class TestClassifyTier:
    def test_synthetic_traffic_routed_to_rule(self) -> None:
        assert classify_tier(severity="SEV-1", description="synthetic probe") == "rule"
        assert classify_tier(severity="SEV-2", description="smoke test") == "rule"

    def test_explicit_false_positive_scenario_routed_to_rule(self) -> None:
        assert classify_tier(severity="SEV-2", description="x", scenario_id="false-positive") == "rule"

    def test_sev1_routed_to_premium(self) -> None:
        assert classify_tier(severity="SEV-1", description="anything") == "premium"
        assert classify_tier(severity="P1", description="anything") == "premium"
        assert classify_tier(severity="CRITICAL", description="anything") == "premium"

    def test_sev2_with_no_runbook_match_routed_to_premium(self) -> None:
        """SEV-2 with no runbook anchor — pay for the premium model."""
        assert classify_tier(severity="SEV-2", description="x", runbook_matched=False) == "premium"

    def test_sev2_default_routed_to_cheap(self) -> None:
        assert classify_tier(severity="SEV-2", description="x") == "cheap"
        assert classify_tier(severity="SEV-2", description="x", runbook_matched=True) == "cheap"

    def test_sev3_default_routed_to_cheap(self) -> None:
        assert classify_tier(severity="SEV-3", description="x") == "cheap"

    def test_no_signal_and_no_runbook_routed_to_rule(self) -> None:
        """When telemetry is silent AND no runbook hits, there's no LLM work to do."""
        assert classify_tier(
            severity="SEV-2",
            description="x",
            has_strong_signal=False,
            runbook_matched=False,
        ) == "rule"


# ──────────────────────────────────────────────────────────────────────────
# Counters
# ──────────────────────────────────────────────────────────────────────────


class TestCounters:
    def test_submit_increments_counters_per_tier(self) -> None:
        COUNTERS.record_submit("cheap")
        COUNTERS.record_submit("cheap")
        COUNTERS.record_submit("premium")
        snap = COUNTERS.snapshot()
        assert snap["submitted_total"] == 3
        assert snap["by_tier_submitted"]["cheap"] == 2
        assert snap["by_tier_submitted"]["premium"] == 1

    def test_queued_active_derived_correctly(self) -> None:
        COUNTERS.record_submit("cheap")
        COUNTERS.record_submit("cheap")
        COUNTERS.record_submit("cheap")
        # Two have started, none completed → queued=1, active=2
        COUNTERS.record_start()
        COUNTERS.record_start()
        snap = COUNTERS.snapshot()
        assert snap["queued"] == 1
        assert snap["active"] == 2
        # One completes → queued=1, active=1
        COUNTERS.record_complete("cheap")
        snap = COUNTERS.snapshot()
        assert snap["queued"] == 1
        assert snap["active"] == 1
        assert snap["by_tier_completed"]["cheap"] == 1

    def test_llm_calls_per_minute_window(self) -> None:
        for _ in range(5):
            COUNTERS.record_llm_call()
        assert COUNTERS.llm_calls_last_60s() == 5
        # Stuff a stale timestamp into the window and confirm it's trimmed.
        COUNTERS._llm_window.appendleft(time.time() - 120.0)
        assert COUNTERS.llm_calls_last_60s() == 5  # the stale entry got dropped


# ──────────────────────────────────────────────────────────────────────────
# Worker pool
# ──────────────────────────────────────────────────────────────────────────


class TestWorkerPool:
    def test_executor_respects_max_concurrent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SRE_MAX_CONCURRENT_INVESTIGATIONS", "2")
        reset_executor()
        ex = get_executor()
        assert ex._max_workers == 2

    def test_submit_job_records_counters(self) -> None:
        future = submit_job(lambda: 42, tier="premium")
        assert future.result(timeout=5) == 42
        snap = COUNTERS.snapshot()
        assert snap["submitted_total"] == 1
        assert snap["started_total"] == 1
        assert snap["completed_total"] == 1
        assert snap["by_tier_submitted"]["premium"] == 1
        assert snap["by_tier_completed"]["premium"] == 1

    def test_burst_queues_beyond_max_concurrent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Submitting more jobs than max_concurrent must not error and must
        eventually complete all of them. Mid-flight we should see queued > 0.
        """
        monkeypatch.setenv("SRE_MAX_CONCURRENT_INVESTIGATIONS", "2")
        reset_executor()

        # Slow jobs so we can see queue depth before they finish.
        start_barrier = []

        def slow():
            start_barrier.append(1)
            time.sleep(0.3)
            return "ok"

        futures = [submit_job(slow, tier="cheap") for _ in range(8)]

        # Briefly poll for the "queue depth visible" condition. We don't
        # assert an exact queue depth (timing is racy) but we DO assert
        # queued > 0 at some point during the burst.
        deadline = time.time() + 2.0
        saw_queue = False
        while time.time() < deadline:
            snap = COUNTERS.snapshot()
            if snap["queued"] > 0:
                saw_queue = True
                break
            time.sleep(0.02)
        assert saw_queue, "expected queued > 0 during burst, never observed"

        # All eight must eventually complete.
        for f in futures:
            assert f.result(timeout=5) == "ok"

        snap = COUNTERS.snapshot()
        assert snap["completed_total"] == 8
        assert snap["queued"] == 0
        assert snap["active"] == 0


# ──────────────────────────────────────────────────────────────────────────
# Job exceptions still update completion counters
# ──────────────────────────────────────────────────────────────────────────


def test_failed_job_still_completes_counter() -> None:
    """If the user's target raises, we still record completion (active drains)."""
    def boom():
        raise RuntimeError("kaboom")

    future = submit_job(boom, tier="cheap")
    with pytest.raises(RuntimeError):
        future.result(timeout=5)
    snap = COUNTERS.snapshot()
    assert snap["completed_total"] == 1
    assert snap["by_tier_completed"]["cheap"] == 1
    # If completion didn't fire, `active` would still be 1.
    assert snap["active"] == 0
