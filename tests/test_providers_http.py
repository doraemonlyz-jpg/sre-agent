"""
Tests for sre_agent.providers._http -- D1 shared HTTP plumbing.

Coverage:
  * Auth header construction (none / bearer / basic).
  * Retry on 429 / 5xx, then succeed.
  * Retry on TimeoutException, then succeed.
  * Exhaust retries -> last response or last exception is propagated.
  * Self-metrics increment (sre_provider_requests_total + latency).
  * probe_health returns ok=True / status_code=200 on success.
  * probe_health returns ok=False with redacted error on failure.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from sre_agent.providers._http import (
    RetryingClient,
    _build_auth_header,
    make_retrying_client,
    probe_health,
)


# ──────────────────────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────────────────────


class TestAuthHeader:
    def test_no_env_returns_empty(self, monkeypatch):
        for k in [
            "PROMETHEUS_BEARER_TOKEN",
            "PROMETHEUS_BASIC_AUTH_USER",
            "PROMETHEUS_BASIC_AUTH_PASSWORD",
        ]:
            monkeypatch.delenv(k, raising=False)
        assert _build_auth_header("PROMETHEUS") == {}

    def test_bearer_token_wins_over_basic(self, monkeypatch):
        monkeypatch.setenv("LOKI_BEARER_TOKEN", "abc123")
        monkeypatch.setenv("LOKI_BASIC_AUTH_USER", "user")
        monkeypatch.setenv("LOKI_BASIC_AUTH_PASSWORD", "pass")
        h = _build_auth_header("LOKI")
        assert h == {"Authorization": "Bearer abc123"}

    def test_basic_auth_when_no_bearer(self, monkeypatch):
        monkeypatch.delenv("LOKI_BEARER_TOKEN", raising=False)
        monkeypatch.setenv("LOKI_BASIC_AUTH_USER", "alice")
        monkeypatch.setenv("LOKI_BASIC_AUTH_PASSWORD", "secret")
        h = _build_auth_header("LOKI")
        assert "Authorization" in h
        assert h["Authorization"].startswith("Basic ")
        # Decode and check
        import base64
        decoded = base64.b64decode(h["Authorization"][6:]).decode()
        assert decoded == "alice:secret"

    def test_basic_auth_requires_both_parts(self, monkeypatch):
        monkeypatch.delenv("LOKI_BEARER_TOKEN", raising=False)
        monkeypatch.setenv("LOKI_BASIC_AUTH_USER", "alice")
        monkeypatch.delenv("LOKI_BASIC_AUTH_PASSWORD", raising=False)
        assert _build_auth_header("LOKI") == {}


# ──────────────────────────────────────────────────────────────────────────
# Retry behaviour
# ──────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fast_retry_client():
    """A RetryingClient with near-zero backoff so tests don't sleep."""
    inner = httpx.Client(base_url="http://test.invalid")
    return RetryingClient(
        inner,
        provider_name="test",
        max_attempts=3,
        base_delay_s=0.0,
        max_delay_s=0.0,
    )


class TestRetryBehaviour:
    def test_first_call_success_no_retry(self, fast_retry_client):
        with respx.mock(base_url="http://test.invalid") as mock:
            route = mock.get("/q").respond(200, json={"ok": True})
            r = fast_retry_client.get("/q")
            assert r.status_code == 200
            assert route.call_count == 1

    def test_retry_on_503_then_success(self, fast_retry_client):
        with respx.mock(base_url="http://test.invalid") as mock:
            route = mock.get("/q").mock(
                side_effect=[
                    httpx.Response(503, json={"err": "down"}),
                    httpx.Response(200, json={"ok": True}),
                ]
            )
            r = fast_retry_client.get("/q")
            assert r.status_code == 200
            assert route.call_count == 2

    def test_retry_on_429_then_success(self, fast_retry_client):
        with respx.mock(base_url="http://test.invalid") as mock:
            mock.get("/q").mock(
                side_effect=[
                    httpx.Response(429),
                    httpx.Response(200, json={}),
                ]
            )
            assert fast_retry_client.get("/q").status_code == 200

    def test_retry_on_timeout_then_success(self, fast_retry_client):
        with respx.mock(base_url="http://test.invalid") as mock:
            mock.get("/q").mock(
                side_effect=[
                    httpx.TimeoutException("slow"),
                    httpx.Response(200, json={"ok": True}),
                ]
            )
            assert fast_retry_client.get("/q").status_code == 200

    def test_exhausted_retries_returns_last_response(self, fast_retry_client):
        with respx.mock(base_url="http://test.invalid") as mock:
            route = mock.get("/q").mock(
                return_value=httpx.Response(503, json={"err": "always_down"})
            )
            r = fast_retry_client.get("/q")
            # All 3 attempts retried; last one returned
            assert r.status_code == 503
            assert route.call_count == 3

    def test_exhausted_timeouts_raise(self, fast_retry_client):
        with respx.mock(base_url="http://test.invalid") as mock:
            mock.get("/q").mock(side_effect=httpx.TimeoutException("nope"))
            with pytest.raises(httpx.TimeoutException):
                fast_retry_client.get("/q")

    def test_4xx_not_retried(self, fast_retry_client):
        with respx.mock(base_url="http://test.invalid") as mock:
            route = mock.get("/q").mock(return_value=httpx.Response(404))
            r = fast_retry_client.get("/q")
            assert r.status_code == 404
            assert route.call_count == 1, "4xx should not retry"


# ──────────────────────────────────────────────────────────────────────────
# Self-metrics
# ──────────────────────────────────────────────────────────────────────────


class TestSelfMetrics:
    def test_request_increments_provider_counter(self, fast_retry_client):
        from sre_agent.metrics import PROVIDER_REQUESTS_TOTAL

        def _read(outcome):
            for s in PROVIDER_REQUESTS_TOTAL.collect()[0].samples:
                if (s.name.endswith("_total")
                        and s.labels.get("provider") == "test"
                        and s.labels.get("outcome") == outcome):
                    return s.value
            return 0.0

        before_ok = _read("ok")
        before_retry = _read("retry_503")

        with respx.mock(base_url="http://test.invalid") as mock:
            mock.get("/q").mock(
                side_effect=[
                    httpx.Response(503),
                    httpx.Response(200, json={}),
                ]
            )
            fast_retry_client.get("/q")

        assert _read("ok") == before_ok + 1
        assert _read("retry_503") == before_retry + 1


# ──────────────────────────────────────────────────────────────────────────
# Health probe
# ──────────────────────────────────────────────────────────────────────────


class TestHealthProbe:
    def test_health_ok(self):
        with respx.mock(base_url="http://test.invalid") as mock:
            mock.get("/-/healthy").respond(200, text="OK")
            inner = httpx.Client(base_url="http://test.invalid")
            client = RetryingClient(inner, provider_name="prom", max_attempts=1)
            r = probe_health(client, path="/-/healthy")
            assert r["ok"] is True
            assert r["status_code"] == 200
            assert r["latency_ms"] >= 0

    def test_health_unexpected_status(self):
        with respx.mock(base_url="http://test.invalid") as mock:
            mock.get("/-/healthy").respond(503)
            inner = httpx.Client(base_url="http://test.invalid")
            client = RetryingClient(inner, provider_name="prom", max_attempts=1)
            r = probe_health(client, path="/-/healthy")
            assert r["ok"] is False
            assert r["status_code"] == 503
            assert "unexpected status 503" in r["error"]

    def test_health_network_failure(self):
        with respx.mock(base_url="http://test.invalid") as mock:
            mock.get("/-/healthy").mock(
                side_effect=httpx.ConnectError("conn refused")
            )
            inner = httpx.Client(base_url="http://test.invalid")
            client = RetryingClient(inner, provider_name="prom", max_attempts=1)
            r = probe_health(client, path="/-/healthy")
            assert r["ok"] is False
            assert r["status_code"] is None
            assert "ConnectError" in r["error"]

    def test_health_does_not_retry(self):
        """A wedged backend should fail fast, not after the full retry loop."""
        with respx.mock(base_url="http://test.invalid") as mock:
            route = mock.get("/-/healthy").respond(503)
            inner = httpx.Client(base_url="http://test.invalid")
            client = RetryingClient(inner, provider_name="prom", max_attempts=5)
            probe_health(client, path="/-/healthy")
            assert route.call_count == 1, "health probe must not retry"


# ──────────────────────────────────────────────────────────────────────────
# Builder
# ──────────────────────────────────────────────────────────────────────────


class TestBuilder:
    def test_make_client_applies_auth(self, monkeypatch):
        monkeypatch.setenv("PROMETHEUS_BEARER_TOKEN", "tok")
        client = make_retrying_client(
            base_url="http://test.invalid",
            timeout_s=2.0,
            provider_name="prometheus",
            auth_env_prefix="PROMETHEUS",
        )
        # Inspect the underlying httpx.Client headers
        assert client._inner.headers.get("Authorization") == "Bearer tok"

    def test_make_client_extra_headers(self, monkeypatch):
        monkeypatch.delenv("PROMETHEUS_BEARER_TOKEN", raising=False)
        client = make_retrying_client(
            base_url="http://test.invalid",
            timeout_s=2.0,
            provider_name="prometheus",
            auth_env_prefix="PROMETHEUS",
            extra_headers={"X-Scope-OrgID": "team-a"},
        )
        assert client._inner.headers.get("X-Scope-OrgID") == "team-a"
