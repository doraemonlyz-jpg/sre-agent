"""
CompositeProvider tests — verify each `fetch_*` is dispatched to the right
sub-provider, and unset slots return NO_SIGNAL rather than raising.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from sre_agent.providers import CompositeProvider, get_provider
from sre_agent.providers.loki import LokiProvider
from sre_agent.providers.prometheus import PrometheusProvider
from sre_agent.schemas import EvidenceResult

_T0 = datetime(2026, 5, 11, 14, 30, tzinfo=timezone.utc)
_T1 = _T0 + timedelta(minutes=15)


def _prom_client() -> httpx.Client:
    return httpx.Client(base_url="http://prom:9090")


def _loki_client() -> httpx.Client:
    return httpx.Client(base_url="http://loki:3100")


# ──────────────────────────────────────────────────────────────────────────
# dispatch
# ──────────────────────────────────────────────────────────────────────────


@respx.mock
def test_dispatches_to_metrics_and_logs() -> None:
    """Composite routes metrics→Prometheus, logs→Loki."""
    respx.get("http://prom:9090/api/v1/query_range").mock(
        return_value=httpx.Response(200, json={
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [{
                    "metric": {"service": "x"},
                    "values": [
                        [1_715_000_000, "0.1"],
                        [1_715_000_060, "10.0"],
                    ],
                }],
            },
        })
    )
    respx.get("http://loki:3100/loki/api/v1/query_range").mock(
        return_value=httpx.Response(200, json={
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": [{
                    "stream": {"service": "x"},
                    "values": [["1715000000000000000", "boom"]],
                }],
            },
        })
    )

    comp = CompositeProvider(
        metrics=PrometheusProvider(base_url="http://prom:9090", client=_prom_client()),
        logs=LokiProvider(base_url="http://loki:3100", client=_loki_client()),
    )

    metrics = comp.fetch_metrics(service="x", from_ts=_T0, to_ts=_T1)
    logs = comp.fetch_logs(service="x", from_ts=_T0, to_ts=_T1)

    assert metrics.result == EvidenceResult.FOUND
    assert logs.result == EvidenceResult.FOUND
    assert logs.hits == 1


def test_unset_slots_return_no_signal() -> None:
    """A composite with nothing wired still satisfies the interface."""
    comp = CompositeProvider()
    logs = comp.fetch_logs(service="x", from_ts=_T0, to_ts=_T1)
    metrics = comp.fetch_metrics(service="x", from_ts=_T0, to_ts=_T1)
    traces = comp.fetch_traces(service="x", from_ts=_T0, to_ts=_T1)
    deploys = comp.fetch_deploys(services=["x"], from_ts=_T0, to_ts=_T1)
    assert logs.result == EvidenceResult.NO_SIGNAL
    assert metrics.result == EvidenceResult.NO_SIGNAL
    assert traces.result == EvidenceResult.NO_SIGNAL
    assert deploys.result == EvidenceResult.NO_SIGNAL


# ──────────────────────────────────────────────────────────────────────────
# factory
# ──────────────────────────────────────────────────────────────────────────


def test_get_provider_oss_returns_composite() -> None:
    p = get_provider("oss")
    assert isinstance(p, CompositeProvider)
    assert isinstance(p.metrics_p, PrometheusProvider)
    assert isinstance(p.logs_p, LokiProvider)


@pytest.mark.parametrize("alias", ["oss", "OSS", "open-source", "prom+loki"])
def test_get_provider_oss_aliases(alias: str) -> None:
    p = get_provider(alias)
    assert isinstance(p, CompositeProvider)


def test_get_provider_unknown_raises() -> None:
    with pytest.raises(ValueError):
        get_provider("splunk")
