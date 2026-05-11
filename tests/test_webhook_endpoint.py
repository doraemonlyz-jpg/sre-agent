"""
Integration tests for the /api/alerts/webhook endpoint.

We don't want the LangGraph pipeline to actually run during these tests
(it spawns a daemon thread and can take a few seconds), so we monkeypatch
the dashboard's `_spawn_incident` helper to skip the thread but still
register the incident dict.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    """A Flask test client with the pipeline thread stubbed out."""
    import dashboard.app as dash

    captured: dict = {}

    def _fake_spawn(alert, scenario_id=None):
        captured["alert"] = alert
        captured["scenario_id"] = scenario_id
        incident_id = "test1234ab"
        with dash.INCIDENTS_LOCK:
            dash.INCIDENTS[incident_id] = {
                "id": incident_id,
                "alert": alert.model_dump(mode="json"),
                "phase": "investigating",
                "started_at": 0,
                "events": [],
                "findings": {},
                "hypothesis": None,
                "remediation": None,
            }
        return incident_id

    monkeypatch.setattr(dash, "_spawn_incident", _fake_spawn)

    c = dash.app.test_client()
    c.captured = captured  # type: ignore[attr-defined]
    yield c

    # cleanup
    with dash.INCIDENTS_LOCK:
        dash.INCIDENTS.clear()


def test_webhook_accepts_datadog(client) -> None:
    r = client.post(
        "/api/alerts/webhook",
        json={
            "alert_id": "99",
            "alert_title": "[Triggered] error_rate on checkout-api",
            "priority": "P1",
            "service": "checkout-api",
            "tags": "env:prod,service:checkout-api",
            "date": "2026-05-11T14:30:00Z",
        },
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["phase"] == "investigating"
    alert = client.captured["alert"]
    assert alert.service == "checkout-api"
    assert alert.severity.value == "SEV-1"


def test_webhook_accepts_pagerduty(client) -> None:
    r = client.post(
        "/api/alerts/webhook",
        json={
            "event": {
                "event_type": "incident.triggered",
                "data": {
                    "title": "checkout-api: error rate spiking",
                    "service": {"summary": "checkout-api"},
                    "urgency": "high",
                    "created_at": "2026-05-11T14:30:00Z",
                },
            },
        },
    )
    assert r.status_code == 200
    assert client.captured["alert"].service == "checkout-api"


def test_webhook_accepts_generic(client) -> None:
    r = client.post(
        "/api/alerts/webhook",
        json={"service": "svc-x", "description": "boom", "severity": "high"},
    )
    assert r.status_code == 200
    alert = client.captured["alert"]
    assert alert.service == "svc-x"
    assert alert.severity.value == "SEV-1"


def test_webhook_rejects_garbage(client) -> None:
    r = client.post("/api/alerts/webhook", json={"random": "stuff"})
    assert r.status_code == 400
    assert "source" in r.get_json()["error"].lower()


def test_webhook_explicit_source_header(client) -> None:
    """Caller forces generic adapter via X-SRE-Source header."""
    r = client.post(
        "/api/alerts/webhook",
        json={"service": "svc-q", "description": "hi", "alert_id": "ignored"},
        headers={"X-SRE-Source": "generic"},
    )
    assert r.status_code == 200
    assert client.captured["alert"].service == "svc-q"


def test_webhook_shared_secret_blocks_bad_token(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SRE_WEBHOOK_SECRET", "s3cret")
    r = client.post(
        "/api/alerts/webhook",
        json={"service": "x", "description": "y"},
        headers={"X-SRE-Token": "wrong"},
    )
    assert r.status_code == 401


def test_webhook_shared_secret_allows_correct_token(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SRE_WEBHOOK_SECRET", "s3cret")
    r = client.post(
        "/api/alerts/webhook",
        json={"service": "x", "description": "y"},
        headers={"X-SRE-Token": "s3cret"},
    )
    assert r.status_code == 200
