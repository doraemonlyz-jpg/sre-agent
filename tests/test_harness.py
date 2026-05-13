"""Unit tests for the harness module (L3 observability core)."""

from __future__ import annotations

import threading
import time

import pytest

from sre_agent.harness import (
    RECORDER,
    HarnessCallback,
    LLMCallRecord,
    bind_agent,
    bind_incident,
    record_cache_event,
    record_persona_load,
    record_retry,
)


@pytest.fixture(autouse=True)
def _reset_recorder():
    RECORDER.reset()
    yield
    RECORDER.reset()


# ──────────────────────────────────────────────────────────────────────────
# Context binding
# ──────────────────────────────────────────────────────────────────────────


class TestContextBinding:
    def test_bind_incident_propagates_to_records(self) -> None:
        with bind_incident("inc-abc"):
            record_persona_load("log-detective", "sha123")
        recs = RECORDER.recent()
        assert recs[0].incident_id == "inc-abc"

    def test_bind_incident_resets_on_exit(self) -> None:
        with bind_incident("inc-abc"):
            pass
        record_persona_load("log-detective", "sha123")
        recs = RECORDER.recent()
        assert recs[0].incident_id is None

    def test_bind_agent_sets_prompt_sha(self) -> None:
        with bind_agent("log-detective", prompt_sha="sha999"):
            cb = HarnessCallback()
            cb.on_chat_model_start(
                serialized={"name": "gpt-oss:20b"},
                messages=[[]],
                run_id="r1",
            )
            cb.on_llm_end(_FakeLLMResult(), run_id="r1")
        recs = RECORDER.recent(kind="llm_call")
        assert recs[0].prompt_sha == "sha999"
        assert recs[0].agent == "log-detective"

    def test_context_isolated_between_threads(self) -> None:
        results: dict[str, str | None] = {}

        def worker(tag: str) -> None:
            with bind_incident(f"inc-{tag}"):
                time.sleep(0.05)  # let threads overlap
                record_persona_load("hyp", "x")
                # Find our record after the sleep — the most recent for our incident
                recs = RECORDER.for_incident(f"inc-{tag}")
                results[tag] = recs[-1].incident_id if recs else None

        threads = [threading.Thread(target=worker, args=(t,)) for t in "AB"]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert results["A"] == "inc-A"
        assert results["B"] == "inc-B"


# ──────────────────────────────────────────────────────────────────────────
# Ring buffer
# ──────────────────────────────────────────────────────────────────────────


class TestRingBuffer:
    def test_recent_returns_newest_first(self) -> None:
        for i in range(5):
            record_persona_load(f"agent-{i}", f"sha{i}")
        recs = RECORDER.recent(limit=3)
        assert [r.agent for r in recs] == ["agent-4", "agent-3", "agent-2"]

    def test_recent_filters_by_kind(self) -> None:
        record_persona_load("a", "sha")
        record_cache_event(hit=True, cache_key="k1")
        record_cache_event(hit=False, cache_key="k2")
        record_retry(agent="a", attempt=1, error="timeout")
        hits = RECORDER.recent(kind="cache_hit")
        assert len(hits) == 1
        assert hits[0].kind == "cache_hit"

    def test_for_incident_returns_only_matching(self) -> None:
        with bind_incident("inc-1"):
            record_persona_load("a", "sha")
            record_persona_load("b", "sha")
        with bind_incident("inc-2"):
            record_persona_load("c", "sha")
        assert len(RECORDER.for_incident("inc-1")) == 2
        assert len(RECORDER.for_incident("inc-2")) == 1
        assert len(RECORDER.for_incident("inc-3")) == 0

    def test_summary_shape(self) -> None:
        record_persona_load("a", "sha")
        record_cache_event(hit=True)
        snap = RECORDER.summary()
        assert snap["total_records"] == 2
        assert "by_kind" in snap
        assert snap["by_kind"]["persona_load"] == 1
        assert snap["by_kind"]["cache_hit"] == 1


# ──────────────────────────────────────────────────────────────────────────
# Callback latency / token capture
# ──────────────────────────────────────────────────────────────────────────


class _FakeMessage:
    def __init__(self, content: str, usage: dict | None = None) -> None:
        self.content = content
        self.usage_metadata = usage
        self.response_metadata: dict = {}


class _FakeGen:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeLLMResult:
    def __init__(
        self,
        *,
        prompt_tokens: int | None = 120,
        completion_tokens: int | None = 30,
        usage_in_llm_output: bool = True,
    ) -> None:
        if usage_in_llm_output:
            self.llm_output = {
                "token_usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
            }
        else:
            self.llm_output = {}
        msg = _FakeMessage("hello")
        self.generations = [[_FakeGen(msg)]]


class TestCallback:
    def test_latency_is_computed(self) -> None:
        cb = HarnessCallback()
        cb.on_chat_model_start(serialized={"name": "m1"}, messages=[[]], run_id="r1")
        time.sleep(0.02)
        cb.on_llm_end(_FakeLLMResult(), run_id="r1")
        rec = RECORDER.recent()[0]
        assert rec.latency_ms is not None
        assert rec.latency_ms >= 18  # allow scheduler jitter

    def test_token_usage_parsed_from_llm_output(self) -> None:
        cb = HarnessCallback()
        cb.on_chat_model_start(serialized={"name": "m1"}, messages=[[]], run_id="r1")
        cb.on_llm_end(_FakeLLMResult(prompt_tokens=200, completion_tokens=50), run_id="r1")
        rec = RECORDER.recent()[0]
        assert rec.input_tokens == 200
        assert rec.output_tokens == 50

    def test_error_marks_status(self) -> None:
        cb = HarnessCallback()
        cb.on_chat_model_start(serialized={"name": "m1"}, messages=[[]], run_id="r2")
        cb.on_llm_error(TimeoutError("boom"), run_id="r2")
        rec = RECORDER.recent()[0]
        assert rec.status == "error"
        assert "Timeout" in (rec.error or "")

    def test_unknown_run_id_is_ignored(self) -> None:
        cb = HarnessCallback()
        # No matching on_chat_model_start — should silently no-op rather than crash.
        cb.on_llm_end(_FakeLLMResult(), run_id="nope")
        assert RECORDER.summary()["total_records"] == 0


# ──────────────────────────────────────────────────────────────────────────
# Eviction / ring-buffer overflow
# ──────────────────────────────────────────────────────────────────────────


def test_overflow_evicts_oldest():
    from sre_agent.harness import HarnessRecorder

    small = HarnessRecorder(max_records=3)
    for i in range(5):
        small.record(LLMCallRecord(id=f"r{i}", kind="persona_load", ts=0, agent="x"))
    assert len(small.recent(limit=100)) == 3
    ids = [r.id for r in small.recent(limit=100)]
    assert ids == ["r4", "r3", "r2"]  # newest first, oldest evicted
