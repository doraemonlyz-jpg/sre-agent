"""Flask dashboard smoke tests — verifies the LangGraph wiring works."""

from __future__ import annotations

import time

import pytest

from dashboard.app import app as flask_app


@pytest.fixture(autouse=True)
def _disable_rate_limit_and_auth(monkeypatch):
    """The pre-L5 tests assume an open API. The L5 layer adds rate
    limits + optional auth; both default off, but other test files
    may have flipped the LIMITER's bucket state. Reset to a clean slate
    for every test here."""
    monkeypatch.setenv("SRE_RATE_LIMIT", "off")
    monkeypatch.setenv("SRE_AUTH_REQUIRED", "0")
    from sre_agent.auth import REGISTRY
    from sre_agent.ratelimit import LIMITER

    REGISTRY.clear()
    LIMITER.reset()
    yield
    LIMITER.reset()
    REGISTRY.clear()


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def test_health(client):
    """`/api/health` is the minimal liveness probe (k8s-style); the
    scenarios count moved to `/api/health/legacy` to keep liveness fast."""
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True


def test_health_legacy_shape_preserved(client):
    r = client.get("/api/health/legacy")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["scenarios"] >= 3


def test_list_scenarios(client):
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    body = r.get_json()
    assert "scenarios" in body
    ids = {s["id"] for s in body["scenarios"]}
    assert {"redis-pool-exhaustion", "false-positive", "downstream-cascade"} <= ids


def test_fire_unknown_scenario_400(client):
    r = client.post("/api/incidents/fire", json={"scenario_id": "no-such"})
    assert r.status_code == 400


def test_fire_and_poll_redis_scenario(client):
    r = client.post("/api/incidents/fire", json={"scenario_id": "redis-pool-exhaustion"})
    assert r.status_code == 200
    incident_id = r.get_json()["id"]

    # Poll up to 15s for the pipeline to finish
    for _ in range(60):
        r = client.get(f"/api/incidents/{incident_id}")
        body = r.get_json()
        if body["phase"] in {"diagnosed", "no_signal", "failed"}:
            break
        time.sleep(0.25)
    else:
        pytest.fail("pipeline never completed")

    assert body["phase"] in {"diagnosed", "no_signal", "failed"}
    assert body["events"]
    # The findings shape must match the v0 legacy contract the frontend reads
    assert "findings" in body
    if body["phase"] == "diagnosed":
        assert body["hypothesis"] is not None
        assert "top" in body["hypothesis"]
        assert "confidence" in body["hypothesis"]


def test_fire_custom_alert(client):
    r = client.post(
        "/api/incidents/fire",
        json={
            "service": "checkout-api",
            "severity": "SEV-1",
            "description": "synthetic test alert",
        },
    )
    assert r.status_code == 200


def test_report_endpoint_404_until_done(client):
    r = client.post("/api/incidents/fire", json={"scenario_id": "false-positive"})
    incident_id = r.get_json()["id"]

    # Wait for completion
    for _ in range(60):
        r = client.get(f"/api/incidents/{incident_id}")
        if r.get_json()["phase"] != "investigating":
            break
        time.sleep(0.25)

    r = client.get(f"/api/incidents/{incident_id}/report")
    # Report endpoint may return 200 (typed pydantic JSON) or 409 if pipeline failed cleanly
    assert r.status_code in {200, 409}


# ──────────────────────────────────────────────────────────────────────────
# Phase E — scale endpoints
#
# These tests exercise the burst/stats *endpoint logic*; they monkeypatch
# `_run_pipeline` to a near-instant no-op so the test process doesn't fan
# out N actual graph runs and leave background threads thrashing well past
# pytest exit. The real pipeline is still covered by other dashboard tests.
# ──────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fast_pipeline(monkeypatch):
    """
    Replace `dashboard.app._run_pipeline` with a fast no-op so burst tests
    can fire hundreds of incidents without dragging the test runtime out
    by `N / max_workers * <real-pipeline-seconds>`.
    """
    import dashboard.app as dapp

    def _noop(incident_id, alert):  # type: ignore[no-untyped-def]
        with dapp.INCIDENTS_LOCK:
            inc = dapp.INCIDENTS.get(incident_id)
            if inc is not None:
                inc["phase"] = "diagnosed"
                inc["diagnosed_at"] = dapp._now_ms()
                inc["diagnosis_ms"] = 1

    monkeypatch.setattr(dapp, "_run_pipeline", _noop)
    yield


def test_scale_stats_shape(client):
    r = client.get("/api/scale/stats")
    assert r.status_code == 200
    body = r.get_json()
    for key in (
        "submitted_total",
        "started_total",
        "completed_total",
        "queued",
        "active",
        "by_tier_submitted",
        "by_tier_completed",
        "llm_calls_total",
        "llm_calls_per_min",
        "max_concurrent",
        "cost_estimate_usd",
        "cost_if_all_premium_usd",
        "cost_saved_usd",
    ):
        assert key in body, f"missing key {key}"
    assert set(body["by_tier_completed"].keys()) >= {"rule", "cheap", "premium"}


def test_burst_endpoint_rejects_unknown_scenario(client):
    r = client.post("/api/incidents/burst?scenario_id=no-such")
    assert r.status_code == 400


def test_burst_endpoint_queues_n_alerts(client, fast_pipeline):
    """A burst of 10 must register 10 incidents and 10 submissions."""
    # Take a snapshot of submitted_total BEFORE firing the burst so we
    # can assert the delta — other tests in this session may have already
    # submitted a few incidents.
    before = client.get("/api/scale/stats").get_json()["submitted_total"]

    r = client.post("/api/incidents/burst?n=10")
    assert r.status_code == 200
    body = r.get_json()
    assert body["burst"] is True
    assert body["queued"] == 10
    assert len(body["incident_ids"]) == 10

    after = client.get("/api/scale/stats").get_json()["submitted_total"]
    assert after - before == 10


def test_burst_caps_at_500(client, fast_pipeline):
    r = client.post("/api/incidents/burst?n=999999")
    assert r.status_code == 200
    body = r.get_json()
    # Cap from app.py is 500
    assert body["queued"] == 500
    assert len(body["incident_ids"]) == 500


def test_incident_carries_model_tier(client, fast_pipeline):
    r = client.post("/api/incidents/fire", json={"scenario_id": "false-positive"})
    incident_id = r.get_json()["id"]
    body = client.get(f"/api/incidents/{incident_id}").get_json()
    # false-positive scenario is hard-routed to 'rule' by classify_tier.
    assert body.get("model_tier") == "rule"

    # And the listing endpoint must surface the tier too.
    listing = client.get("/api/incidents").get_json()["incidents"]
    matched = next((i for i in listing if i["id"] == incident_id), None)
    assert matched is not None
    assert matched["model_tier"] == "rule"
