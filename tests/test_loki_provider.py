"""
LokiProvider tests. respx-mocks /loki/api/v1/query_range against the
real Loki response shape.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from sre_agent.providers.loki import LokiProvider
from sre_agent.schemas import EvidenceResult

_T0 = datetime(2026, 5, 11, 14, 30, tzinfo=timezone.utc)
_T1 = _T0 + timedelta(minutes=15)


@pytest.fixture
def provider() -> LokiProvider:
    client = httpx.Client(base_url="http://loki:3100")
    return LokiProvider(base_url="http://loki:3100", client=client)


# ──────────────────────────────────────────────────────────────────────────
# happy paths
# ──────────────────────────────────────────────────────────────────────────


@respx.mock
def test_fetch_logs_parses_real_shape(provider: LokiProvider) -> None:
    """Loki streams response → LogsEvidence with bucketed messages."""
    respx.get("http://loki:3100/loki/api/v1/query_range").mock(
        return_value=httpx.Response(200, json={
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": [
                    {
                        "stream": {
                            "service": "chaos-app",
                            "level": "error",
                            "container": "chaos-app-1",
                        },
                        "values": [
                            ["1715000000000000000", "redis.exceptions.ConnectionError: Connection refused"],
                            ["1715000060000000000", "redis.exceptions.ConnectionError: Connection refused"],
                            ["1715000120000000000", "redis.exceptions.ConnectionError: Connection refused"],
                            ["1715000180000000000", "timeout calling downstream:redis after 5s"],
                        ],
                    },
                ],
            },
        })
    )

    ev = provider.fetch_logs(service="chaos-app", from_ts=_T0, to_ts=_T1)

    assert ev.result == EvidenceResult.FOUND
    assert ev.hits == 4
    # Top message buckets by count.
    assert ev.top_messages[0]["count"] == 3
    assert "Connection refused" in ev.top_messages[0]["message"]
    # First/peak timestamps come from ns timestamps.
    assert ev.first_at is not None
    assert ev.peak_at is not None
    assert ev.first_at <= ev.peak_at
    # Citation carries the stream labels.
    assert any("service=chaos-app" in c for c in ev.citations)


@respx.mock
def test_fetch_logs_empty_window(provider: LokiProvider) -> None:
    respx.get("http://loki:3100/loki/api/v1/query_range").mock(
        return_value=httpx.Response(200, json={
            "status": "success",
            "data": {"resultType": "streams", "result": []},
        })
    )
    ev = provider.fetch_logs(service="quiet", from_ts=_T0, to_ts=_T1)
    assert ev.result == EvidenceResult.NO_SIGNAL
    assert ev.hits == 0


@respx.mock
def test_fetch_logs_multi_stream_aggregation(provider: LokiProvider) -> None:
    """Loki can return multiple streams (one per label set) — we sum across them."""
    respx.get("http://loki:3100/loki/api/v1/query_range").mock(
        return_value=httpx.Response(200, json={
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": [
                    {
                        "stream": {"service": "chaos-app", "pod": "pod-a"},
                        "values": [
                            ["1715000000000000000", "error A"],
                            ["1715000010000000000", "error A"],
                        ],
                    },
                    {
                        "stream": {"service": "chaos-app", "pod": "pod-b"},
                        "values": [
                            ["1715000020000000000", "error B"],
                            ["1715000030000000000", "error B"],
                            ["1715000040000000000", "error B"],
                        ],
                    },
                ],
            },
        })
    )
    ev = provider.fetch_logs(service="chaos-app", from_ts=_T0, to_ts=_T1)
    assert ev.hits == 5
    assert ev.top_messages[0] == {"message": "error B", "count": 3}


@respx.mock
def test_fetch_logs_api_error_returns_error(provider: LokiProvider) -> None:
    respx.get("http://loki:3100/loki/api/v1/query_range").mock(
        return_value=httpx.Response(503, text="loki down")
    )
    ev = provider.fetch_logs(service="x", from_ts=_T0, to_ts=_T1)
    assert ev.result == EvidenceResult.ERROR
    assert ev.hits == 0


@respx.mock
def test_fetch_logs_non_success_status_returns_error(provider: LokiProvider) -> None:
    """Loki sometimes returns 200 with status='error' in the body."""
    respx.get("http://loki:3100/loki/api/v1/query_range").mock(
        return_value=httpx.Response(200, json={
            "status": "error",
            "errorType": "bad_data",
            "error": "parse error",
        })
    )
    ev = provider.fetch_logs(service="x", from_ts=_T0, to_ts=_T1)
    assert ev.result == EvidenceResult.ERROR


# ──────────────────────────────────────────────────────────────────────────
# capability declarations
# ──────────────────────────────────────────────────────────────────────────


def test_unsupported_methods_return_no_signal(provider: LokiProvider) -> None:
    metrics = provider.fetch_metrics(service="x", from_ts=_T0, to_ts=_T1)
    traces = provider.fetch_traces(service="x", from_ts=_T0, to_ts=_T1)
    deploys = provider.fetch_deploys(services=["x"], from_ts=_T0, to_ts=_T1)
    assert metrics.result == EvidenceResult.NO_SIGNAL
    assert traces.result == EvidenceResult.NO_SIGNAL
    assert deploys.result == EvidenceResult.NO_SIGNAL
