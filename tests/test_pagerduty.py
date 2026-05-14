"""
Tests for sre_agent.notifications.pagerduty -- D4.

Coverage:
  * Default construction without routing key -> dry_run = True.
  * Explicit routing_key -> not dry_run; POSTs to /v2/enqueue with the
    correct payload shape.
  * Severity gating: SEV-3 below default min_severity is filtered.
  * acknowledge / resolve build minimal payloads.
  * Network failure returns sent=False with the exception in `error`.
  * Non-2xx response returns sent=False with the body in `error`.
  * Self-metric `sre_pagerduty_events_total` increments per outcome.
  * Flask /api/incidents/<id>/page integration test (dry-run + with key).
"""

from __future__ import annotations

import os

import httpx
import pytest
import respx

from sre_agent.notifications import PagerDutyNotifier, PagerDutyResult


# ──────────────────────────────────────────────────────────────────────────
# Construction + dry-run defaulting
# ──────────────────────────────────────────────────────────────────────────


class TestConstruction:
    def test_no_routing_key_implies_dry_run(self, monkeypatch):
        monkeypatch.delenv("PAGERDUTY_ROUTING_KEY", raising=False)
        n = PagerDutyNotifier.from_env()
        assert n.dry_run is True
        assert n.routing_key is None

    def test_explicit_routing_key_disables_dry_run(self, monkeypatch):
        monkeypatch.setenv("PAGERDUTY_ROUTING_KEY", "abc123")
        monkeypatch.delenv("SRE_PAGERDUTY_DRY_RUN", raising=False)
        n = PagerDutyNotifier.from_env()
        assert n.dry_run is False
        assert n.routing_key == "abc123"

    def test_explicit_dry_run_overrides_routing_key(self, monkeypatch):
        monkeypatch.setenv("PAGERDUTY_ROUTING_KEY", "abc123")
        monkeypatch.setenv("SRE_PAGERDUTY_DRY_RUN", "true")
        n = PagerDutyNotifier.from_env()
        assert n.dry_run is True


# ──────────────────────────────────────────────────────────────────────────
# trigger() dry-run + payload shape
# ──────────────────────────────────────────────────────────────────────────


class TestTriggerDryRun:
    def test_dry_run_returns_payload_no_network(self, monkeypatch):
        monkeypatch.delenv("PAGERDUTY_ROUTING_KEY", raising=False)
        n = PagerDutyNotifier()  # no client constructed
        result = n.trigger(
            incident_id="inc-1",
            service="checkout-api",
            severity="SEV-1",
            summary="db down",
        )
        assert isinstance(result, PagerDutyResult)
        assert result.sent is False
        assert result.dry_run is True
        assert result.event_action == "trigger"
        assert result.dedup_key == "inc-1"
        assert result.payload["event_action"] == "trigger"
        assert result.payload["dedup_key"] == "inc-1"
        assert result.payload["payload"]["severity"] == "critical"
        assert result.payload["payload"]["component"] == "checkout-api"
        assert result.payload["routing_key"] == "DRY_RUN"

    def test_summary_truncated_to_1024(self):
        n = PagerDutyNotifier(dry_run=True)
        long = "x" * 5000
        result = n.trigger(
            incident_id="i",
            service="s",
            severity="SEV-1",
            summary=long,
        )
        assert len(result.payload["payload"]["summary"]) == 1024


# ──────────────────────────────────────────────────────────────────────────
# trigger() real path with respx
# ──────────────────────────────────────────────────────────────────────────


class TestTriggerReal:
    def test_posts_to_pd_with_correct_shape(self):
        with respx.mock(assert_all_called=True) as mock:
            route = mock.post("https://events.pagerduty.com/v2/enqueue").respond(
                202,
                json={"status": "success", "dedup_key": "pd-abc"},
            )
            client = httpx.Client()
            n = PagerDutyNotifier(
                routing_key="abc123",
                dry_run=False,
                client=client,
            )
            result = n.trigger(
                incident_id="inc-42",
                service="payments",
                severity="SEV-2",
                summary="latency spike",
                details={"trace_id": "x"},
            )
            assert result.sent is True
            assert result.status == 202
            assert result.pd_dedup_key_returned == "pd-abc"
            assert route.called

            sent_body = route.calls.last.request.read().decode()
            import json as _json
            parsed = _json.loads(sent_body)
            assert parsed["routing_key"] == "abc123"
            assert parsed["dedup_key"] == "inc-42"
            assert parsed["payload"]["severity"] == "error"

    def test_http_5xx_returns_sent_false_with_error(self):
        with respx.mock() as mock:
            mock.post("https://events.pagerduty.com/v2/enqueue").respond(
                503, text="upstream down"
            )
            client = httpx.Client()
            n = PagerDutyNotifier(routing_key="k", dry_run=False, client=client)
            result = n.trigger(
                incident_id="i", service="s", severity="SEV-1", summary="x"
            )
            assert result.sent is False
            assert result.status == 503
            assert "503" in result.error
            assert "upstream down" in result.error

    def test_network_error_caught(self):
        with respx.mock() as mock:
            mock.post("https://events.pagerduty.com/v2/enqueue").mock(
                side_effect=httpx.ConnectError("refused")
            )
            client = httpx.Client()
            n = PagerDutyNotifier(routing_key="k", dry_run=False, client=client)
            result = n.trigger(
                incident_id="i", service="s", severity="SEV-1", summary="x"
            )
            assert result.sent is False
            assert "ConnectError" in result.error


# ──────────────────────────────────────────────────────────────────────────
# Severity gating
# ──────────────────────────────────────────────────────────────────────────


class TestSeverityGate:
    def test_sev3_below_default_min_sev2_is_filtered(self):
        n = PagerDutyNotifier(dry_run=True, min_severity="SEV-2")
        result = n.trigger(
            incident_id="i", service="s", severity="SEV-3", summary="meh"
        )
        assert result.sent is False
        assert "below min_severity" in result.error

    def test_sev2_passes_at_default(self):
        n = PagerDutyNotifier(dry_run=True, min_severity="SEV-2")
        result = n.trigger(
            incident_id="i", service="s", severity="SEV-2", summary="x"
        )
        assert result.dry_run is True
        assert result.error is None

    def test_min_sev_can_be_lowered(self):
        n = PagerDutyNotifier(dry_run=True, min_severity="SEV-3")
        result = n.trigger(
            incident_id="i", service="s", severity="SEV-3", summary="x"
        )
        assert result.dry_run is True


# ──────────────────────────────────────────────────────────────────────────
# acknowledge / resolve
# ──────────────────────────────────────────────────────────────────────────


class TestLifecycle:
    def test_acknowledge_payload_minimal(self):
        n = PagerDutyNotifier(dry_run=True)
        r = n.acknowledge(incident_id="inc-9")
        assert r.event_action == "acknowledge"
        # PagerDuty expects only routing_key + event_action + dedup_key
        # for ack/resolve -- no `payload` block.
        assert "payload" not in r.payload
        assert r.payload["dedup_key"] == "inc-9"

    def test_resolve_payload_minimal(self):
        n = PagerDutyNotifier(dry_run=True)
        r = n.resolve(incident_id="inc-9")
        assert r.event_action == "resolve"
        assert "payload" not in r.payload
        assert r.payload["dedup_key"] == "inc-9"

    def test_acknowledge_real_path(self):
        with respx.mock() as mock:
            mock.post("https://events.pagerduty.com/v2/enqueue").respond(
                202, json={"status": "success"}
            )
            client = httpx.Client()
            n = PagerDutyNotifier(routing_key="k", dry_run=False, client=client)
            r = n.acknowledge(incident_id="abc")
            assert r.sent is True
            assert r.event_action == "acknowledge"


# ──────────────────────────────────────────────────────────────────────────
# Self-metrics
# ──────────────────────────────────────────────────────────────────────────


class TestMetrics:
    def test_dry_run_increments_counter(self):
        from sre_agent.metrics import PAGERDUTY_EVENTS_TOTAL

        def _read(action, sev, outcome):
            for s in PAGERDUTY_EVENTS_TOTAL.collect()[0].samples:
                if (s.name.endswith("_total")
                        and s.labels.get("event_type") == action
                        and s.labels.get("severity") == sev
                        and s.labels.get("outcome") == outcome):
                    return s.value
            return 0.0

        before = _read("trigger", "SEV-1", "dry_run")
        n = PagerDutyNotifier(dry_run=True)
        n.trigger(incident_id="m1", service="s", severity="SEV-1", summary="x")
        assert _read("trigger", "SEV-1", "dry_run") == before + 1

    def test_real_ok_increments_ok(self):
        from sre_agent.metrics import PAGERDUTY_EVENTS_TOTAL

        def _read():
            for s in PAGERDUTY_EVENTS_TOTAL.collect()[0].samples:
                if (s.name.endswith("_total")
                        and s.labels.get("event_type") == "trigger"
                        and s.labels.get("severity") == "SEV-2"
                        and s.labels.get("outcome") == "ok"):
                    return s.value
            return 0.0

        before = _read()
        with respx.mock() as mock:
            mock.post("https://events.pagerduty.com/v2/enqueue").respond(
                202, json={"status": "success"}
            )
            n = PagerDutyNotifier(
                routing_key="k", dry_run=False, client=httpx.Client(),
            )
            n.trigger(incident_id="m2", service="s", severity="SEV-2", summary="x")
        assert _read() == before + 1


# ──────────────────────────────────────────────────────────────────────────
# Flask integration
# ──────────────────────────────────────────────────────────────────────────


class TestFlaskIntegration:
    def test_page_endpoint_returns_dry_run_payload(self, monkeypatch):
        monkeypatch.delenv("PAGERDUTY_ROUTING_KEY", raising=False)
        from dashboard.app import INCIDENTS, app

        # Inject a synthetic diagnosed incident.
        INCIDENTS["test-incident-pd"] = {
            "id": "test-incident-pd",
            "phase": "diagnosed",
            "alert": {"service": "pay", "severity": "SEV-1"},
            "hypothesis": {"root_cause": "redis pool exhausted"},
            "remediation": {"actions": []},
        }
        try:
            client = app.test_client()
            r = client.post("/api/incidents/test-incident-pd/page")
            assert r.status_code == 200
            data = r.get_json()
            assert data["dry_run"] is True
            assert data["sent"] is False
            assert data["event_action"] == "trigger"
            assert data["dedup_key"] == "test-incident-pd"
            assert data["payload"]["payload"]["severity"] == "critical"
        finally:
            INCIDENTS.pop("test-incident-pd", None)

    def test_page_endpoint_404_for_unknown_incident(self):
        from dashboard.app import app
        client = app.test_client()
        r = client.post("/api/incidents/does-not-exist/page")
        assert r.status_code == 404
