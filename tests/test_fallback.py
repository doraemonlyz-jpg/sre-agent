"""
Tests for sre_agent.models.fallback -- B4 LLM fallback chains.

Coverage:
  * Primary tier success (no fallback fires).
  * Recovery on cheap tier (1 transition recorded).
  * Recovery on rule tier (2 transitions recorded).
  * All-tiers-fail re-raises the LAST exception.
  * Timeout enforcement.
  * with_structured_output composes through tiers.
  * Rule-based responder yields a schema-valid degraded instance.
  * Harness records the fallback events.
  * Prometheus counter increments on each transition.
"""

from __future__ import annotations

import threading
import time

import pytest
from pydantic import BaseModel, Field

from sre_agent.harness import RECORDER
from sre_agent.models.fallback import (
    FallbackChainModel,
    RuleBasedDegradedModel,
    Tier,
    _build_degraded_instance,
    build_chain_from_factory_funcs,
)


# ──────────────────────────────────────────────────────────────────────────
# Stub models for tests
# ──────────────────────────────────────────────────────────────────────────


class _AlwaysOK:
    """A 'model' that always returns the given content."""

    def __init__(self, response: str = "OK"):
        self.response = response
        self.invocations = 0

    def invoke(self, _input, **_kwargs):
        self.invocations += 1
        return self.response

    def with_structured_output(self, schema):
        return _AlwaysOKStructured(schema, self.response)


class _AlwaysOKStructured:
    def __init__(self, schema, response):
        self.schema = schema
        self.response = response

    def invoke(self, _input, **_kwargs):
        # Construct an instance whatever the schema is.
        if hasattr(self.schema, "model_fields"):
            args = {}
            for fname, finfo in self.schema.model_fields.items():
                ann = finfo.annotation
                if ann is str:
                    args[fname] = self.response
                elif ann is int:
                    args[fname] = 42
                elif ann is float:
                    args[fname] = 0.5
                else:
                    args[fname] = None
            return self.schema(**args)
        return self.response


class _AlwaysRaises:
    def __init__(self, exc: BaseException):
        self.exc = exc
        self.invocations = 0

    def invoke(self, _input, **_kwargs):
        self.invocations += 1
        raise self.exc

    def with_structured_output(self, _schema):
        return self  # same instance, still raises


class _SlowModel:
    def __init__(self, sleep_seconds: float, response: str = "slow"):
        self.sleep_seconds = sleep_seconds
        self.response = response
        self.invocations = 0

    def invoke(self, _input, **_kwargs):
        self.invocations += 1
        time.sleep(self.sleep_seconds)
        return self.response

    def with_structured_output(self, _schema):
        return self


# ──────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────


class TestSuccessPaths:
    def test_primary_tier_success_no_fallback(self):
        primary = _AlwaysOK("primary-result")
        chain = build_chain_from_factory_funcs(
            "test-agent",
            [("primary", lambda: primary, 5.0)],
        )
        result = chain.invoke("hello")
        assert result == "primary-result"
        assert primary.invocations == 1

    def test_recovers_on_second_tier(self):
        primary = _AlwaysRaises(RuntimeError("boom"))
        cheap = _AlwaysOK("cheap-result")
        chain = build_chain_from_factory_funcs(
            "test-agent",
            [
                ("premium", lambda: primary, 5.0),
                ("cheap", lambda: cheap, 5.0),
            ],
        )
        result = chain.invoke("hello")
        assert result == "cheap-result"
        assert primary.invocations == 1
        assert cheap.invocations == 1

    def test_recovers_on_third_tier(self):
        primary = _AlwaysRaises(RuntimeError("boom1"))
        cheap = _AlwaysRaises(RuntimeError("boom2"))
        rule = RuleBasedDegradedModel("rule")
        chain = build_chain_from_factory_funcs(
            "test-agent",
            [
                ("premium", lambda: primary, 5.0),
                ("cheap", lambda: cheap, 5.0),
                ("rule", lambda: rule, None),
            ],
        )
        result = chain.invoke("hello")
        # Rule-based returns an AIMessage; check it's the degraded one.
        assert "DEGRADED MODE" in str(getattr(result, "content", result))


class TestFailurePaths:
    def test_all_tiers_fail_raises_last_exception(self):
        e1 = RuntimeError("boom1")
        e2 = ValueError("boom2")
        chain = build_chain_from_factory_funcs(
            "test-agent",
            [
                ("premium", lambda: _AlwaysRaises(e1), 5.0),
                ("cheap", lambda: _AlwaysRaises(e2), 5.0),
            ],
        )
        with pytest.raises(ValueError, match="boom2"):
            chain.invoke("hello")

    def test_empty_chain_rejected_at_construction(self):
        with pytest.raises(ValueError, match="at least one tier"):
            FallbackChainModel("test", [])

    def test_timeout_triggers_fallback(self):
        slow = _SlowModel(sleep_seconds=0.5)
        fast = _AlwaysOK("fast")
        chain = build_chain_from_factory_funcs(
            "test-agent",
            [
                ("premium", lambda: slow, 0.1),  # 100ms timeout, sleep is 500ms
                ("cheap", lambda: fast, 5.0),
            ],
        )
        result = chain.invoke("hello")
        assert result == "fast"


class TestStructuredOutput:
    class DummySchema(BaseModel):
        verdict: str = Field(default="unknown")
        confidence: float = Field(default=0.0)

    def test_structured_output_propagates_to_tier(self):
        chain = build_chain_from_factory_funcs(
            "test-agent",
            [("primary", lambda: _AlwaysOK("hit"), 5.0)],
        )
        wrapped = chain.with_structured_output(self.DummySchema)
        result = wrapped.invoke("hello")
        assert isinstance(result, self.DummySchema)
        assert result.verdict == "hit"

    def test_structured_output_falls_through_to_rule_tier(self):
        chain = build_chain_from_factory_funcs(
            "test-agent",
            [
                ("premium", lambda: _AlwaysRaises(RuntimeError("nope")), 5.0),
                ("rule", lambda: RuleBasedDegradedModel("rule"), None),
            ],
        )
        wrapped = chain.with_structured_output(self.DummySchema)
        result = wrapped.invoke("hello")
        # Rule tier returns a degraded instance of the schema
        assert isinstance(result, self.DummySchema)
        assert result.verdict == "DEGRADED"


class TestRuleBasedResponder:
    def test_invoke_returns_degraded_aimessage(self):
        rule = RuleBasedDegradedModel("rule")
        msg = rule.invoke("anything")
        assert "DEGRADED MODE" in str(msg.content)

    def test_structured_yields_schema_valid_placeholder(self):
        class S(BaseModel):
            top: str = Field(default="")
            n: int = Field(default=0)

        rule = RuleBasedDegradedModel("rule")
        out = rule.with_structured_output(S).invoke("ignored")
        assert isinstance(out, S)
        assert out.top == "DEGRADED"
        assert out.n == 0

    def test_build_degraded_instance_handles_lists_and_dicts(self):
        class S(BaseModel):
            items: list = Field(default_factory=list)
            tags: dict = Field(default_factory=dict)

        out = _build_degraded_instance(S)
        assert isinstance(out, S)
        assert out.items == []
        assert out.tags == {}


class TestObservability:
    def test_harness_records_fallback_transition(self):
        primary = _AlwaysRaises(RuntimeError("boom"))
        cheap = _AlwaysOK("ok")
        chain = build_chain_from_factory_funcs(
            "obs-agent",
            [
                ("premium", lambda: primary, 5.0),
                ("cheap", lambda: cheap, 5.0),
            ],
        )

        before = len([
            r for r in RECORDER.recent(limit=1000)
            if r.kind == "fallback" and r.agent == "obs-agent"
        ])

        chain.invoke("x")

        after_records = [
            r for r in RECORDER.recent(limit=1000)
            if r.kind == "fallback" and r.agent == "obs-agent"
        ]
        assert len(after_records) == before + 1
        rec = after_records[0]
        assert rec.detail["from_tier"] == "premium"
        assert rec.detail["to_tier"] == "cheap"
        assert rec.detail["reason"] == "runtimeerror"

    def test_prometheus_counter_increments_on_transition(self):
        from sre_agent.metrics import LLM_FALLBACKS_TOTAL

        # Read pre-state by sampling the counter for our specific labels.
        def _read():
            samples = LLM_FALLBACKS_TOTAL.collect()[0].samples
            return [
                s for s in samples
                if s.labels.get("agent") == "metric-agent"
                and s.labels.get("from_tier") == "premium"
                and s.labels.get("to_tier") == "cheap"
                and s.labels.get("reason") == "runtimeerror"
                and s.name.endswith("_total")
            ]

        before = sum(s.value for s in _read())

        primary = _AlwaysRaises(RuntimeError("boom"))
        cheap = _AlwaysOK("ok")
        chain = build_chain_from_factory_funcs(
            "metric-agent",
            [
                ("premium", lambda: primary, 5.0),
                ("cheap", lambda: cheap, 5.0),
            ],
        )
        chain.invoke("x")

        after = sum(s.value for s in _read())
        assert after >= before + 1


class TestThreadSafety:
    def test_concurrent_invocations_dont_clobber(self):
        primary = _AlwaysOK("primary")
        chain = build_chain_from_factory_funcs(
            "ts-agent",
            [("primary", lambda: primary, 5.0)],
        )
        results: list[str] = []
        lock = threading.Lock()

        def worker():
            r = chain.invoke("x")
            with lock:
                results.append(r)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 8
        assert all(r == "primary" for r in results)
        assert primary.invocations == 8


class TestTierLazyBuild:
    def test_secondary_tier_only_built_when_needed(self):
        primary = _AlwaysOK("primary")
        cheap_built = {"count": 0}

        def build_cheap():
            cheap_built["count"] += 1
            return _AlwaysOK("cheap")

        chain = build_chain_from_factory_funcs(
            "lazy-agent",
            [
                ("primary", lambda: primary, 5.0),
                ("cheap", build_cheap, 5.0),
            ],
        )
        chain.invoke("hello")
        assert cheap_built["count"] == 0, "secondary tier should not be built on primary success"
