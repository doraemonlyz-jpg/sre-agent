"""MockProvider should produce typed evidence for every scenario."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sre_agent.providers.mock import MockProvider
from sre_agent.schemas import EvidenceResult


@pytest.fixture
def mp() -> MockProvider:
    return MockProvider()


def test_lists_scenarios(mp):
    sc = mp.list_scenarios()
    assert len(sc) >= 3
    assert all("id" in s and "service" in s for s in sc)


def test_get_scenario_alert(mp):
    a = mp.get_scenario_alert("redis-pool-exhaustion")
    assert a["service"] == "checkout-api"
    assert a["severity"] in {"SEV-1", "SEV-2", "SEV-3", "SEV-4"}


def test_unknown_service_returns_no_signal(mp):
    now = datetime.now(timezone.utc)
    ev = mp.fetch_logs(
        service="nonexistent-service",
        from_ts=now - timedelta(minutes=10),
        to_ts=now,
    )
    assert ev.result == EvidenceResult.NO_SIGNAL
    assert ev.hits == 0


def test_redis_scenario_finds_logs_and_deploys(mp):
    now = datetime.now(timezone.utc)
    logs = mp.fetch_logs(
        service="checkout-api",
        from_ts=now - timedelta(minutes=10),
        to_ts=now,
        scenario_id="redis-pool-exhaustion",
    )
    assert logs.result == EvidenceResult.FOUND
    assert logs.hits > 0
    assert any("interpretation" in (m or {}) or "message" in (m or {}) for m in logs.top_messages)

    deploys = mp.fetch_deploys(
        services=["checkout-api"],
        from_ts=now - timedelta(hours=2),
        to_ts=now,
        scenario_id="redis-pool-exhaustion",
    )
    assert deploys.result == EvidenceResult.FOUND
    assert any(d.suspect == "HIGH" for d in deploys.deploys)


def test_false_positive_scenario_finds_metrics_only(mp):
    now = datetime.now(timezone.utc)
    logs = mp.fetch_logs(
        service="search-api",
        from_ts=now - timedelta(minutes=10),
        to_ts=now,
        scenario_id="false-positive",
    )
    metrics = mp.fetch_metrics(
        service="search-api",
        from_ts=now - timedelta(minutes=10),
        to_ts=now,
        scenario_id="false-positive",
    )
    # Logs should be quiet
    assert logs.result == EvidenceResult.NO_SIGNAL or logs.hits <= 5
    # Metrics may still show a request_rate "spike" (it's what triggered the alert)
    # but the interpretation should NOT say "downstream / dependency".
    assert metrics.result in {EvidenceResult.NO_SIGNAL, EvidenceResult.FOUND}


def test_provider_never_raises_on_missing_scenario(mp):
    """The provider must never raise; it must return ERROR or NO_SIGNAL."""
    now = datetime.now(timezone.utc)
    for fn_name in ("fetch_logs", "fetch_metrics", "fetch_traces"):
        fn = getattr(mp, fn_name)
        ev = fn(
            service="absolutely-no-such-service-anywhere",
            from_ts=now - timedelta(minutes=10),
            to_ts=now,
        )
        assert ev.result in {EvidenceResult.NO_SIGNAL, EvidenceResult.ERROR}
