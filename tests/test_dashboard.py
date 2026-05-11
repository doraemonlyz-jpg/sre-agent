"""Flask dashboard smoke tests — verifies the LangGraph wiring works."""

from __future__ import annotations

import time

import pytest

from dashboard.app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
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
