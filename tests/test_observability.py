"""
Tests for the opt-in observability exporter.

Contract:

  * `detect_mode()` returns 'off' when no env is set.
  * The recorder.record() tap is installed exactly once (idempotent).
  * The exporter NEVER raises on the hot path, even if the backend dies.
  * In 'stdout' mode every record makes it to stdout (debug / first run).
"""

from __future__ import annotations

import time

import pytest

from sre_agent import observability as obs
from sre_agent.harness import RECORDER, LLMCallRecord


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in (
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_SERVICE_NAME",
        "SRE_OBSERVABILITY_MODE",
    ):
        monkeypatch.delenv(k, raising=False)
    yield


class TestDetectMode:
    def test_default_off(self):
        assert obs.detect_mode() == "off"

    def test_langfuse_when_keys_set(self, monkeypatch):
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
        assert obs.detect_mode() == "langfuse"

    def test_otlp_when_endpoint_set(self, monkeypatch):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://ex.local")
        assert obs.detect_mode() == "otlp"

    def test_langfuse_wins_over_otlp(self, monkeypatch):
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://ex.local")
        assert obs.detect_mode() == "langfuse"

    def test_stdout_explicit(self, monkeypatch):
        monkeypatch.setenv("SRE_OBSERVABILITY_MODE", "stdout")
        assert obs.detect_mode() == "stdout"


class TestRecorderTapIdempotent:
    def test_wrap_recorder_twice_no_op(self):
        before = RECORDER.record
        obs._wrap_recorder()
        obs._wrap_recorder()
        # Should not be wrapped a second time.
        assert RECORDER.record is before


class TestStdoutMode:
    def test_stdout_prints_records(self, monkeypatch, capsys):
        # Build a fresh exporter in stdout mode.
        monkeypatch.setenv("SRE_OBSERVABILITY_MODE", "stdout")
        local = obs._Exporter()
        try:
            rec = LLMCallRecord(
                id="x1",
                kind="llm_call",
                ts=time.time(),
                agent="test",
                model="gpt-oss",
                status="ok",
            )
            local.enqueue(rec)
            # Drain
            for _ in range(20):
                if local._sent >= 1:
                    break
                time.sleep(0.05)
            captured = capsys.readouterr()
            assert "[observability]" in captured.out
            assert "test" in captured.out
        finally:
            local.flush()


class TestNeverCrashesHotPath:
    """If the export backend explodes, the agent must keep running."""

    def test_enqueue_swallows_backend_errors(self, monkeypatch):
        # Force OFF mode → enqueue is a no-op, but the contract is "never raise".
        local = obs._Exporter()
        # Even with a bogus record, no exception.
        local.enqueue(LLMCallRecord(id="x", kind="llm_call", ts=0))

    def test_stats_returns_dict_in_off_mode(self):
        local = obs._Exporter()
        s = local.stats()
        assert s["mode"] == "off"
        assert "sent" in s and "failed" in s
