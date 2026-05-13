"""Tests for the response cache + retry helper."""

from __future__ import annotations

import time

import pytest

from sre_agent.cache import CACHE, IncidentCache, cache_key, store, try_get
from sre_agent.harness import RECORDER
from sre_agent.retry import is_retryable, with_retries


@pytest.fixture(autouse=True)
def _reset_state():
    CACHE.reset()
    RECORDER.reset()
    yield
    CACHE.reset()
    RECORDER.reset()


# ──────────────────────────────────────────────────────────────────────────
# Cache key normalization
# ──────────────────────────────────────────────────────────────────────────


class TestCacheKey:
    def test_same_alert_collapses_to_same_key(self) -> None:
        # Different digits in description should NOT cause a miss — the alert
        # rule is the same, just newer numbers.
        a = cache_key("checkout-api", "SEV-2", "error_rate=0.07 sustained for 12s")
        b = cache_key("checkout-api", "SEV-2", "error_rate=0.09 sustained for 18s")
        assert a == b

    def test_different_service_distinct_keys(self) -> None:
        a = cache_key("a", "SEV-2", "x")
        b = cache_key("b", "SEV-2", "x")
        assert a != b

    def test_severity_part_of_key(self) -> None:
        assert cache_key("a", "SEV-1", "x") != cache_key("a", "SEV-3", "x")

    def test_case_normalized(self) -> None:
        assert cache_key("Checkout-API", "sev-2", "Foo") == cache_key(
            "checkout-api", "SEV-2", "FOO"
        )


# ──────────────────────────────────────────────────────────────────────────
# Get / put / ttl
# ──────────────────────────────────────────────────────────────────────────


class TestCache:
    def test_miss_then_hit(self) -> None:
        key = cache_key("checkout-api", "SEV-2", "errs")
        assert CACHE.get(key) is None
        CACHE.put(key, "inc-1", {"phase": "diagnosed"})
        got = CACHE.get(key)
        assert got is not None
        cid, payload = got
        assert cid == "inc-1"
        assert payload["phase"] == "diagnosed"

    def test_stats(self) -> None:
        key = cache_key("s", "SEV-2", "d")
        CACHE.get(key)  # miss
        CACHE.put(key, "inc", {})
        CACHE.get(key)  # hit
        CACHE.get(key)  # hit
        stats = CACHE.stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["inserts"] == 1
        assert 0.0 < stats["hit_rate"] < 1.0

    def test_invalidate(self) -> None:
        key = cache_key("s", "SEV-2", "d")
        CACHE.put(key, "inc", {})
        assert CACHE.invalidate(key) is True
        assert CACHE.get(key) is None
        assert CACHE.invalidate(key) is False  # idempotent

    def test_ttl_expires(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SRE_CACHE_TTL_SECONDS", "0.05")
        key = cache_key("s", "SEV-2", "d")
        CACHE.put(key, "inc", {"phase": "diagnosed"})
        assert CACHE.get(key) is not None
        time.sleep(0.06)
        assert CACHE.get(key) is None

    def test_sweep_drops_expired(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SRE_CACHE_TTL_SECONDS", "0.05")
        # cache_key intentionally normalizes digits (so re-fired alerts with
        # newer numbers collapse), so distinct keys need distinct words.
        for word in ("redis", "deploy", "downstream"):
            CACHE.put(cache_key("s", "SEV-2", word), f"inc-{word}", {})
        time.sleep(0.06)
        dropped = CACHE.sweep()
        assert dropped == 3


# ──────────────────────────────────────────────────────────────────────────
# Convenience wrappers emit harness events
# ──────────────────────────────────────────────────────────────────────────


class TestHarnessIntegration:
    def test_try_get_records_miss(self) -> None:
        assert try_get("checkout-api", "SEV-2", "x") is None
        recs = RECORDER.recent(kind="cache_miss")
        assert len(recs) == 1

    def test_try_get_records_hit_with_incident_id(self) -> None:
        store("checkout-api", "SEV-2", "x", "inc-1", {"phase": "diagnosed"})
        got = try_get("checkout-api", "SEV-2", "x")
        assert got is not None
        hits = RECORDER.recent(kind="cache_hit")
        assert len(hits) == 1
        assert hits[0].incident_id == "inc-1"

    def test_isolated_cache(self) -> None:
        c = IncidentCache()
        c.put("k", "id", {"phase": "diagnosed"})
        assert c.get("k") is not None
        assert c.get("missing") is None
        assert c.stats()["hits"] == 1
        assert c.stats()["misses"] == 1


# ──────────────────────────────────────────────────────────────────────────
# Retry helper
# ──────────────────────────────────────────────────────────────────────────


class TestRetry:
    def test_retries_on_timeout(self) -> None:
        attempts = {"n": 0}

        def fn() -> str:
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise TimeoutError("upstream timed out")
            return "ok"

        out = with_retries(fn, agent="t", max_attempts=2, base_delay_s=0.001)
        assert out == "ok"
        assert attempts["n"] == 3
        # 2 retry events recorded
        assert len(RECORDER.recent(kind="retry")) == 2

    def test_does_not_retry_validation_error(self) -> None:
        attempts = {"n": 0}

        def fn() -> None:
            attempts["n"] += 1
            raise ValueError("bad schema")

        with pytest.raises(ValueError):
            with_retries(fn, agent="t", max_attempts=2, base_delay_s=0.001)
        assert attempts["n"] == 1
        assert RECORDER.recent(kind="retry") == []

    def test_gives_up_after_max_attempts(self) -> None:
        def fn() -> None:
            raise ConnectionError("never coming back")

        with pytest.raises(ConnectionError):
            with_retries(fn, agent="t", max_attempts=2, base_delay_s=0.001)
        # 2 retry events before giving up
        assert len(RECORDER.recent(kind="retry")) == 2

    def test_is_retryable_classifier(self) -> None:
        assert is_retryable(TimeoutError("read timed out"))
        assert is_retryable(ConnectionError("eof"))
        assert is_retryable(RuntimeError("503 service unavailable"))
        assert not is_retryable(ValueError("bad json"))
        assert not is_retryable(TypeError("nope"))
