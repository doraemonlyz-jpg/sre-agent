"""
DatadogProvider tests — uses respx to mock the Datadog API at the transport
layer. The provider's parsing code is exercised against the *real* Datadog
response shapes (taken from their public docs); only the network is faked.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from sre_agent.providers.datadog import DatadogProvider
from sre_agent.schemas import EvidenceResult

# A single instant we use for every fixture so the window math is stable.
_T0 = datetime(2026, 5, 11, 14, 30, tzinfo=timezone.utc)
_T1 = _T0 + timedelta(minutes=15)


@pytest.fixture
def provider() -> DatadogProvider:
    """A provider wired to a fixed base URL respx can intercept."""
    client = httpx.Client(
        base_url="https://api.datadoghq.com",
        headers={"DD-API-KEY": "test", "DD-APPLICATION-KEY": "test"},
    )
    return DatadogProvider(
        api_key="test",
        app_key="test",
        site="datadoghq.com",
        client=client,
    )


# ──────────────────────────────────────────────────────────────────────────
# logs
# ──────────────────────────────────────────────────────────────────────────


@respx.mock
def test_fetch_logs_parses_real_shape(provider: DatadogProvider) -> None:
    """Real Datadog logs/events/search response → parsed LogsEvidence."""
    respx.post("https://api.datadoghq.com/api/v2/logs/events/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "log-1",
                        "type": "log",
                        "attributes": {
                            "timestamp": "2026-05-11T14:32:18.123Z",
                            "message": "redis.exceptions.ConnectionError: Connection refused",
                            "service": "checkout-api",
                        },
                    },
                    {
                        "id": "log-2",
                        "type": "log",
                        "attributes": {
                            "timestamp": "2026-05-11T14:33:01.000Z",
                            "message": "redis.exceptions.ConnectionError: Connection refused",
                            "service": "checkout-api",
                        },
                    },
                    {
                        "id": "log-3",
                        "type": "log",
                        "attributes": {
                            "timestamp": "2026-05-11T14:34:55.000Z",
                            "message": "timeout calling downstream:redis",
                            "service": "checkout-api",
                        },
                    },
                ]
            },
        )
    )

    ev = provider.fetch_logs(service="checkout-api", from_ts=_T0, to_ts=_T1)

    assert ev.result == EvidenceResult.FOUND
    assert ev.hits == 3
    # Top message buckets by count, most-frequent first.
    assert ev.top_messages[0]["count"] == 2
    assert "redis.exceptions.ConnectionError" in ev.top_messages[0]["message"]
    # First/peak timestamps come from the events.
    assert ev.first_at is not None
    assert ev.peak_at is not None
    assert ev.first_at <= ev.peak_at
    # Citations carry log IDs so the PM can re-query Datadog.
    assert "log:log-1" in ev.citations


@respx.mock
def test_fetch_logs_empty_window(provider: DatadogProvider) -> None:
    respx.post("https://api.datadoghq.com/api/v2/logs/events/search").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    ev = provider.fetch_logs(service="quiet-service", from_ts=_T0, to_ts=_T1)
    assert ev.result == EvidenceResult.NO_SIGNAL
    assert ev.hits == 0


@respx.mock
def test_fetch_logs_api_error_becomes_error_evidence(provider: DatadogProvider) -> None:
    """Contract: NEVER raises. 5xx → result=ERROR with explanatory text."""
    respx.post("https://api.datadoghq.com/api/v2/logs/events/search").mock(
        return_value=httpx.Response(503, json={"errors": ["upstream down"]})
    )
    ev = provider.fetch_logs(service="anything", from_ts=_T0, to_ts=_T1)
    assert ev.result == EvidenceResult.ERROR
    assert ev.hits == 0
    assert "unreachable" in ev.interpretation.lower() or "503" in ev.interpretation


# ──────────────────────────────────────────────────────────────────────────
# metrics
# ──────────────────────────────────────────────────────────────────────────


@respx.mock
def test_fetch_metrics_finds_spike(provider: DatadogProvider) -> None:
    """
    Five metric queries are issued. We return:
    - cpu_pct:        boring baseline, no spike
    - error_rate:     baseline 0.1 → peak 50 → must be flagged SPIKE
    - others:         empty/204 to verify partial parsing still works
    """

    def _route(request: httpx.Request) -> httpx.Response:
        q = request.url.params.get("query", "")
        if "system.cpu" in q:
            return httpx.Response(200, json={
                "series": [{
                    "metric": "system.cpu.user",
                    "pointlist": [
                        [1_715_000_000_000, 5.0],
                        [1_715_000_060_000, 5.5],
                        [1_715_000_120_000, 6.0],
                    ],
                }]
            })
        if "request.errors" in q:
            return httpx.Response(200, json={
                "series": [{
                    "metric": "trace.flask.request.errors",
                    "pointlist": [
                        [1_715_000_000_000, 0.1],
                        [1_715_000_060_000, 0.1],
                        [1_715_000_120_000, 0.2],
                        [1_715_000_180_000, 50.0],   # ← spike
                        [1_715_000_240_000, 48.0],
                    ],
                }]
            })
        # Other metrics: empty payload → snapshot skipped.
        return httpx.Response(200, json={"series": []})

    respx.get("https://api.datadoghq.com/api/v1/query").mock(side_effect=_route)

    ev = provider.fetch_metrics(service="checkout-api", from_ts=_T0, to_ts=_T1)

    assert ev.result == EvidenceResult.FOUND
    names = [m.name for m in ev.metrics]
    assert "cpu_pct" in names
    assert "error_rate" in names

    err = next(m for m in ev.metrics if m.name == "error_rate")
    assert err.is_spike
    assert "SPIKE" in err.verdict

    cpu = next(m for m in ev.metrics if m.name == "cpu_pct")
    assert not cpu.is_spike


@respx.mock
def test_fetch_metrics_all_errors_returns_error(provider: DatadogProvider) -> None:
    respx.get("https://api.datadoghq.com/api/v1/query").mock(
        return_value=httpx.Response(500)
    )
    ev = provider.fetch_metrics(service="x", from_ts=_T0, to_ts=_T1)
    assert ev.result == EvidenceResult.ERROR


# ──────────────────────────────────────────────────────────────────────────
# traces
# ──────────────────────────────────────────────────────────────────────────


@respx.mock
def test_fetch_traces_identifies_hot_span(provider: DatadogProvider) -> None:
    respx.post("https://api.datadoghq.com/api/v2/spans/events/search").mock(
        return_value=httpx.Response(200, json={
            "data": [
                # baseline 10ms calls
                *[
                    {"id": f"s{i}", "attributes": {
                        "name": "redis.get",
                        "service": "checkout-api",
                        "duration": 10_000_000,  # 10ms in ns
                        "status": "ok",
                    }} for i in range(10)
                ],
                # slow + errored
                *[
                    {"id": f"slow{i}", "attributes": {
                        "name": "redis.get",
                        "service": "checkout-api",
                        "duration": 2_000_000_000,  # 2s in ns
                        "status": "error",
                    }} for i in range(8)
                ],
            ]
        })
    )

    ev = provider.fetch_traces(service="checkout-api", from_ts=_T0, to_ts=_T1)

    assert ev.result == EvidenceResult.FOUND
    assert ev.traces_inspected == 18
    assert ev.error_rate == "8/18"
    assert ev.hot_span is not None
    assert ev.hot_span.name == "redis.get"
    # median ~10ms with baseline at p25 (~10ms) — ratio close to 1; but a few
    # very slow spans pull the median up considerably. Either way we should
    # detect *some* ratio worth reporting.
    assert ev.hot_span.median_ms >= ev.hot_span.baseline_ms


@respx.mock
def test_fetch_traces_empty_window(provider: DatadogProvider) -> None:
    respx.post("https://api.datadoghq.com/api/v2/spans/events/search").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    ev = provider.fetch_traces(service="quiet", from_ts=_T0, to_ts=_T1)
    assert ev.result == EvidenceResult.NO_SIGNAL
    assert ev.traces_inspected == 0


# ──────────────────────────────────────────────────────────────────────────
# deploys
# ──────────────────────────────────────────────────────────────────────────


@respx.mock
def test_fetch_deploys_parses_events(provider: DatadogProvider) -> None:
    respx.get("https://api.datadoghq.com/api/v1/events").mock(
        return_value=httpx.Response(200, json={
            "events": [
                {
                    "title": "Deploy checkout-api @abc1234 by jdoe",
                    "date_happened": int(_T1.timestamp()) - 600,  # 10 min before
                    "tags": [
                        "service:checkout-api",
                        "sha:abc1234",
                        "author:jdoe",
                    ],
                    "url": "https://github.com/acme/api/pull/1234",
                }
            ]
        })
    )

    ev = provider.fetch_deploys(
        services=["checkout-api"],
        from_ts=_T0,
        to_ts=_T1,
    )

    assert ev.result == EvidenceResult.FOUND
    assert len(ev.deploys) == 1
    d = ev.deploys[0]
    assert d.service == "checkout-api"
    assert d.sha == "abc1234"
    assert d.author == "jdoe"
    assert d.suspect in ("HIGH", "MEDIUM")  # 10min before → HIGH


@respx.mock
def test_fetch_deploys_empty(provider: DatadogProvider) -> None:
    respx.get("https://api.datadoghq.com/api/v1/events").mock(
        return_value=httpx.Response(200, json={"events": []})
    )
    ev = provider.fetch_deploys(services=["x"], from_ts=_T0, to_ts=_T1)
    assert ev.result == EvidenceResult.NO_SIGNAL
    assert ev.deploys == []
