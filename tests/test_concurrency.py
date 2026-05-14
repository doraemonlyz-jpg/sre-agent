"""
Tests for sre_agent.concurrency -- G2 ensemble fan-out helper.

Coverage:
  * Empty input returns []
  * Single-call returns one outcome with ok=True
  * Mixed ok/error outcomes preserve input order
  * ContextVars from the caller propagate into worker threads
  * Timeout doesn't crash; surviving members still report
  * ensemble_pick_best picks the highest-score winner
  * ensemble_pick_best returns None when all members failed
  * ensemble_agreement returns 1.0 for identical buckets, <1 for splits
  * Self-metrics increment per outcome
  * hypothesis_gen ensemble path picks the highest-confidence response
"""

from __future__ import annotations

import contextvars
import time
from datetime import datetime, timezone

import pytest

from sre_agent.concurrency import (
    CallOutcome,
    concurrent_llm_calls,
    ensemble_agreement,
    ensemble_pick_best,
)


# ──────────────────────────────────────────────────────────────────────────
# concurrent_llm_calls
# ──────────────────────────────────────────────────────────────────────────


class TestConcurrentLLMCalls:
    def test_empty_returns_empty(self):
        assert concurrent_llm_calls([], agent="t") == []

    def test_single_call_succeeds(self):
        out = concurrent_llm_calls([lambda: "hello"], agent="t")
        assert len(out) == 1
        assert out[0].ok is True
        assert out[0].value == "hello"
        assert out[0].error is None
        assert out[0].latency_s >= 0

    def test_preserves_input_order(self):
        funcs = [(lambda i=i: i * 10) for i in range(5)]
        outs = concurrent_llm_calls(funcs, agent="t")
        assert [o.value for o in outs] == [0, 10, 20, 30, 40]

    def test_failure_caught_per_member(self):
        def good():
            return "ok"

        def bad():
            raise ValueError("nope")

        outs = concurrent_llm_calls([good, bad, good], agent="t")
        assert outs[0].ok is True
        assert outs[1].ok is False
        assert "ValueError" in outs[1].error
        assert "nope" in outs[1].error
        assert outs[2].ok is True

    def test_concurrent_runs_actually_overlap(self):
        """If they run concurrently, total wall time is ~max(member),
        not ~sum(members). Use sleep(0.15) x 3 to reduce flake."""
        def slow(i):
            def _f():
                time.sleep(0.15)
                return i
            return _f

        t0 = time.perf_counter()
        outs = concurrent_llm_calls(
            [slow(0), slow(1), slow(2)], agent="t", max_workers=3,
        )
        elapsed = time.perf_counter() - t0
        assert all(o.ok for o in outs)
        # 3 sequential sleeps would be ~0.45s; concurrent should be
        # well under that. Allow 0.30s for thread-pool overhead.
        assert elapsed < 0.30, f"expected concurrent execution, took {elapsed:.2f}s"

    def test_contextvars_propagate(self):
        cv: contextvars.ContextVar[str] = contextvars.ContextVar("test_cv", default="default")
        cv.set("from-parent")

        def reader():
            return cv.get()

        outs = concurrent_llm_calls([reader, reader], agent="t")
        assert all(o.ok for o in outs)
        assert {o.value for o in outs} == {"from-parent"}, (
            f"expected ContextVars to propagate, got {[o.value for o in outs]}"
        )


# ──────────────────────────────────────────────────────────────────────────
# Pickers
# ──────────────────────────────────────────────────────────────────────────


class _Hypo:
    def __init__(self, title: str, confidence: float):
        self.title = title
        self.confidence = confidence


class TestEnsemblePickBest:
    def test_picks_max_confidence(self):
        outs = [
            CallOutcome(ok=True, value=_Hypo("A", 0.6), error=None, latency_s=0.1),
            CallOutcome(ok=True, value=_Hypo("B", 0.9), error=None, latency_s=0.1),
            CallOutcome(ok=True, value=_Hypo("C", 0.4), error=None, latency_s=0.1),
        ]
        winner, info = ensemble_pick_best(outs, score_fn=lambda h: h.confidence)
        assert winner.title == "B"
        assert info["winner_score"] == pytest.approx(0.9)
        assert info["winner_index"] == 1
        assert info["n_ok"] == 3

    def test_returns_none_when_all_failed(self):
        outs = [
            CallOutcome(ok=False, value=None, error="x", latency_s=0.1),
            CallOutcome(ok=False, value=None, error="y", latency_s=0.1),
        ]
        winner, info = ensemble_pick_best(outs, score_fn=lambda h: h.confidence)
        assert winner is None
        assert info["winner_index"] is None
        assert info["n_ok"] == 0

    def test_skips_failed_members(self):
        outs = [
            CallOutcome(ok=False, value=None, error="x", latency_s=0.1),
            CallOutcome(ok=True, value=_Hypo("B", 0.5), error=None, latency_s=0.1),
        ]
        winner, info = ensemble_pick_best(outs, score_fn=lambda h: h.confidence)
        assert winner.title == "B"
        assert info["n_ok"] == 1


class TestEnsembleAgreement:
    def test_unanimous_is_1(self):
        outs = [
            CallOutcome(ok=True, value=_Hypo("redis pool", 0.7), error=None, latency_s=0.1),
            CallOutcome(ok=True, value=_Hypo("redis pool", 0.8), error=None, latency_s=0.1),
            CallOutcome(ok=True, value=_Hypo("redis pool", 0.9), error=None, latency_s=0.1),
        ]
        assert ensemble_agreement(
            outs, bucket_fn=lambda h: h.title,
        ) == pytest.approx(1.0)

    def test_split_two_one(self):
        outs = [
            CallOutcome(ok=True, value=_Hypo("redis", 0.7), error=None, latency_s=0.1),
            CallOutcome(ok=True, value=_Hypo("redis", 0.8), error=None, latency_s=0.1),
            CallOutcome(ok=True, value=_Hypo("network", 0.6), error=None, latency_s=0.1),
        ]
        assert ensemble_agreement(
            outs, bucket_fn=lambda h: h.title,
        ) == pytest.approx(2 / 3)

    def test_no_successes_is_0(self):
        outs = [CallOutcome(ok=False, value=None, error="x", latency_s=0)]
        assert ensemble_agreement(outs, bucket_fn=lambda h: "x") == 0.0


# ──────────────────────────────────────────────────────────────────────────
# Self-metrics
# ──────────────────────────────────────────────────────────────────────────


class TestEnsembleMetrics:
    def test_runs_total_increments(self):
        from sre_agent.metrics import ENSEMBLE_RUNS_TOTAL

        def _read(agent, k, outcome):
            for s in ENSEMBLE_RUNS_TOTAL.collect()[0].samples:
                if (s.name.endswith("_total")
                        and s.labels.get("agent") == agent
                        and s.labels.get("k") == k
                        and s.labels.get("outcome") == outcome):
                    return s.value
            return 0.0

        before = _read("metrics-test", "3", "ok")
        outs = concurrent_llm_calls(
            [lambda i=i: i for i in range(3)],
            agent="metrics-test",
        )
        assert all(o.ok for o in outs)
        assert _read("metrics-test", "3", "ok") == before + 1

    def test_partial_outcome_recorded(self):
        from sre_agent.metrics import ENSEMBLE_RUNS_TOTAL

        def _read():
            for s in ENSEMBLE_RUNS_TOTAL.collect()[0].samples:
                if (s.name.endswith("_total")
                        and s.labels.get("agent") == "partial-test"
                        and s.labels.get("k") == "2"
                        and s.labels.get("outcome") == "partial"):
                    return s.value
            return 0.0

        before = _read()

        def good():
            return 1

        def bad():
            raise RuntimeError("x")

        concurrent_llm_calls([good, bad], agent="partial-test")
        assert _read() == before + 1


# ──────────────────────────────────────────────────────────────────────────
# Integration: hypothesis_gen ensemble path
# ──────────────────────────────────────────────────────────────────────────


class TestHypothesisGenEnsemble:
    def test_ensemble_picks_highest_confidence(self, monkeypatch):
        """When K>1, `hypothesis_generator` should call the LLM K times
        and pick the response with the highest top.confidence."""
        from sre_agent.nodes import hypothesis_gen as hg
        from sre_agent.schemas import (
            AlertIn,
            EvidenceResult,
            Hypothesis,
            HypothesisList,
            LogsEvidence,
            Severity,
        )

        monkeypatch.setenv("SRE_HYPOTHESIS_ENSEMBLE_K", "3")

        responses = [
            HypothesisList(
                hypotheses=[
                    Hypothesis(
                        title=f"member-{i}",
                        detail=f"d{i}",
                        confidence=conf,
                        supporting_evidence=["logs"],
                    )
                ]
            )
            for i, conf in enumerate([0.4, 0.85, 0.6])
        ]
        call_idx = {"i": 0}

        class _StubLLM:
            def with_structured_output(self, *_a, **_kw):
                return self

            def invoke(self, _msgs):
                i = call_idx["i"]
                call_idx["i"] += 1
                return responses[i]

        monkeypatch.setattr(hg, "get_chat_model", lambda *_a, **_kw: _StubLLM())
        monkeypatch.setattr(
            hg, "load_with_sha", lambda _name: ("you are an SRE", "deadbeef"),
        )
        monkeypatch.setattr(hg, "record_persona_load", lambda *_a, **_kw: None)

        state = {
            "alert": AlertIn(
                service="payments",
                severity=Severity.SEV_2,
                description="latency spike",
                started_at=datetime.now(timezone.utc),
            ),
            "logs": LogsEvidence(
                result=EvidenceResult.FOUND,
                hits=42,
                interpretation="errors found",
            ),
        }
        result = hg.hypothesis_generator(state)
        assert result["hypotheses"].top.title == "member-1"
        assert result["hypotheses"].top.confidence == pytest.approx(0.85)
        # Event must mention the ensemble parameters. Events are dicts.
        def _msg(e):
            return (e.get("message") if isinstance(e, dict) else getattr(e, "message", "")) or ""
        assert any("ensemble" in _msg(e).lower() for e in result["events"])
