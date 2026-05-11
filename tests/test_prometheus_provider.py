"""
PrometheusProvider tests. Uses respx to mock /api/v1/query_range against
real Prometheus response shapes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from sre_agent.providers.prometheus import PrometheusProvider
from sre_agent.schemas import EvidenceResult

_T0 = datetime(2026, 5, 11, 14, 30, tzinfo=timezone.utc)
_T1 = _T0 + timedelta(minutes=15)


@pytest.fixture
def provider() -> PrometheusProvider:
    client = httpx.Client(base_url="http://prom:9090")
    return PrometheusProvider(base_url="http://prom:9090", client=client)


# ──────────────────────────────────────────────────────────────────────────
# happy path: a spiking error_rate, flat cpu
# ──────────────────────────────────────────────────────────────────────────


@respx.mock
def test_fetch_metrics_detects_spike(provider: PrometheusProvider) -> None:
    """
    The provider issues 5 query_range calls. We route by the `query` param:
    return a spike for error_rate, flat for cpu_pct, empty for the rest.
    """

    def _route(request: httpx.Request) -> httpx.Response:
        q = request.url.params.get("query", "")
        if "chaos_errors_total" in q:
            return httpx.Response(200, json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [{
                        "metric": {"service": "chaos-app"},
                        "values": [
                            [1_715_000_000, "0.1"],
                            [1_715_000_015, "0.1"],
                            [1_715_000_030, "0.2"],
                            [1_715_000_045, "0.2"],
                            [1_715_000_060, "0.3"],
                            [1_715_000_075, "5.0"],
                            [1_715_000_090, "50.0"],   # ← spike
                            [1_715_000_105, "48.0"],
                            [1_715_000_120, "47.0"],
                            [1_715_000_135, "45.0"],
                        ],
                    }],
                },
            })
        if "process_cpu_seconds_total" in q:
            return httpx.Response(200, json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [{
                        "metric": {"service": "chaos-app"},
                        "values": [
                            [1_715_000_000, "1.0"],
                            [1_715_000_015, "1.1"],
                            [1_715_000_030, "1.05"],
                            [1_715_000_045, "1.0"],
                            [1_715_000_060, "1.1"],
                        ],
                    }],
                },
            })
        # All other metrics: empty result.
        return httpx.Response(200, json={
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
        })

    respx.get("http://prom:9090/api/v1/query_range").mock(side_effect=_route)

    ev = provider.fetch_metrics(service="chaos-app", from_ts=_T0, to_ts=_T1)

    assert ev.result == EvidenceResult.FOUND
    names = {m.name for m in ev.metrics}
    assert "error_rate" in names
    assert "cpu_pct" in names

    err = next(m for m in ev.metrics if m.name == "error_rate")
    assert err.is_spike
    assert "SPIKE" in err.verdict

    cpu = next(m for m in ev.metrics if m.name == "cpu_pct")
    assert not cpu.is_spike


@respx.mock
def test_fetch_metrics_no_data_returns_no_signal(provider: PrometheusProvider) -> None:
    respx.get("http://prom:9090/api/v1/query_range").mock(
        return_value=httpx.Response(
            200,
            json={"status": "success", "data": {"resultType": "matrix", "result": []}},
        )
    )
    ev = provider.fetch_metrics(service="quiet-svc", from_ts=_T0, to_ts=_T1)
    assert ev.result == EvidenceResult.NO_SIGNAL


@respx.mock
def test_fetch_metrics_skips_nan_values(provider: PrometheusProvider) -> None:
    """NaN/Inf string values from Prometheus must not crash the parser."""
    respx.get("http://prom:9090/api/v1/query_range").mock(
        return_value=httpx.Response(200, json={
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [{
                    "metric": {"service": "x"},
                    "values": [
                        [1_715_000_000, "NaN"],
                        [1_715_000_015, "not-a-number"],
                        [1_715_000_030, "1.0"],
                        [1_715_000_045, "10.0"],
                    ],
                }],
            },
        })
    )
    ev = provider.fetch_metrics(service="x", from_ts=_T0, to_ts=_T1)
    # We get at least one valid snapshot rather than crashing.
    assert ev.result in {EvidenceResult.FOUND, EvidenceResult.NO_SIGNAL}


@respx.mock
def test_fetch_metrics_api_error_returns_error(provider: PrometheusProvider) -> None:
    respx.get("http://prom:9090/api/v1/query_range").mock(
        return_value=httpx.Response(500, text="prom is sad")
    )
    ev = provider.fetch_metrics(service="x", from_ts=_T0, to_ts=_T1)
    assert ev.result == EvidenceResult.ERROR


# ──────────────────────────────────────────────────────────────────────────
# capability declarations
# ──────────────────────────────────────────────────────────────────────────


def test_unsupported_methods_return_no_signal(provider: PrometheusProvider) -> None:
    """Prometheus doesn't do logs/traces/deploys — return NO_SIGNAL, never raise."""
    logs = provider.fetch_logs(service="x", from_ts=_T0, to_ts=_T1)
    traces = provider.fetch_traces(service="x", from_ts=_T0, to_ts=_T1)
    deploys = provider.fetch_deploys(services=["x"], from_ts=_T0, to_ts=_T1)
    assert logs.result == EvidenceResult.NO_SIGNAL
    assert traces.result == EvidenceResult.NO_SIGNAL
    assert deploys.result == EvidenceResult.NO_SIGNAL


def test_env_var_query_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """A user with different metric names should be able to override defaults."""
    monkeypatch.setenv("PROM_QUERY_ERROR_RATE", 'my_custom_errors{{svc="{service}"}}')
    p = PrometheusProvider(base_url="http://x")
    assert "my_custom_errors" in p.queries["error_rate"]
