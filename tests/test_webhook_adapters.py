"""
Tests for the webhook payload adapters. Each platform shape → AlertIn.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sre_agent.schemas import Severity
from sre_agent.webhooks import (
    UnknownPayloadError,
    from_datadog_monitor,
    from_generic,
    from_pagerduty,
    parse_alert,
)

# ──────────────────────────────────────────────────────────────────────────
# Datadog Monitor
# ──────────────────────────────────────────────────────────────────────────


def test_datadog_monitor_full_payload() -> None:
    payload = {
        "alert_id": "12345",
        "alert_status": "Triggered",
        "alert_title": "[Triggered] error_rate > 5% on checkout-api",
        "alert_metric": "trace.flask.request.errors",
        "priority": "P1",
        "service": "checkout-api",
        "tags": "env:prod,service:checkout-api,region:us-east-1",
        "date": "2026-05-11T14:30:00.000Z",
        "event_msg": "errors spiking past 5%",
    }
    alert = from_datadog_monitor(payload)
    assert alert.service == "checkout-api"
    assert alert.severity == Severity.SEV_1
    assert "error_rate" in alert.description
    assert "env:prod" in alert.tags
    assert "service:checkout-api" in alert.tags
    assert alert.started_at == datetime(2026, 5, 11, 14, 30, tzinfo=timezone.utc)


def test_datadog_monitor_falls_back_to_service_tag() -> None:
    """If `service` field missing, pull it from the tags string."""
    payload = {
        "alert_title": "alert!",
        "tags": "env:prod,service:fallback-svc",
        "priority": "P3",
    }
    alert = from_datadog_monitor(payload)
    assert alert.service == "fallback-svc"
    assert alert.severity == Severity.SEV_3


def test_datadog_monitor_defaults_severity_when_missing() -> None:
    payload = {"service": "x", "alert_title": "no priority"}
    alert = from_datadog_monitor(payload)
    assert alert.severity == Severity.SEV_2  # default


# ──────────────────────────────────────────────────────────────────────────
# PagerDuty v3
# ──────────────────────────────────────────────────────────────────────────


def test_pagerduty_v3_envelope() -> None:
    payload = {
        "event": {
            "event_type": "incident.triggered",
            "data": {
                "title": "checkout-api: error rate spiking",
                "service": {"id": "PXYZ", "summary": "checkout-api"},
                "urgency": "high",
                "created_at": "2026-05-11T14:30:00Z",
                "teams": [{"summary": "payments"}],
            },
        },
    }
    alert = from_pagerduty(payload)
    assert alert.service == "checkout-api"
    assert alert.severity == Severity.SEV_1  # urgency=high → SEV-1
    assert "checkout-api" in alert.description
    assert "team:payments" in alert.tags


def test_pagerduty_low_urgency_maps_to_sev3() -> None:
    payload = {
        "event": {
            "event_type": "incident.triggered",
            "data": {
                "title": "minor latency",
                "service": {"summary": "background-worker"},
                "urgency": "low",
                "created_at": "2026-05-11T14:30:00Z",
            },
        },
    }
    alert = from_pagerduty(payload)
    assert alert.severity == Severity.SEV_3


# ──────────────────────────────────────────────────────────────────────────
# Generic
# ──────────────────────────────────────────────────────────────────────────


def test_generic_minimal() -> None:
    payload = {"service": "svc-a", "description": "something broke"}
    alert = from_generic(payload)
    assert alert.service == "svc-a"
    assert alert.severity == Severity.SEV_2  # default
    assert alert.description == "something broke"


def test_generic_full() -> None:
    payload = {
        "service": "svc-b",
        "description": "p99 > 2s",
        "severity": "critical",
        "started_at": 1_715_000_000,
        "tags": ["env:prod", "team:platform"],
    }
    alert = from_generic(payload)
    assert alert.severity == Severity.SEV_1
    assert "env:prod" in alert.tags
    assert alert.started_at == datetime.fromtimestamp(1_715_000_000, tz=timezone.utc)


def test_generic_missing_required_field() -> None:
    with pytest.raises(UnknownPayloadError):
        from_generic({"service": "no-description"})


# ──────────────────────────────────────────────────────────────────────────
# parse_alert sniffing
# ──────────────────────────────────────────────────────────────────────────


def test_parse_alert_sniffs_pagerduty() -> None:
    payload = {
        "event": {
            "event_type": "incident.triggered",
            "data": {
                "title": "x",
                "service": {"summary": "svc-x"},
                "urgency": "high",
                "created_at": "2026-05-11T14:30:00Z",
            },
        },
    }
    alert = parse_alert(payload)
    assert alert.service == "svc-x"


def test_parse_alert_sniffs_datadog() -> None:
    payload = {"alert_id": "1", "alert_title": "x", "service": "svc-y"}
    alert = parse_alert(payload)
    assert alert.service == "svc-y"


def test_parse_alert_sniffs_generic() -> None:
    alert = parse_alert({"service": "svc-z", "description": "boom"})
    assert alert.service == "svc-z"


def test_parse_alert_explicit_source_wins() -> None:
    """Even with a Datadog-looking payload, if caller says generic we obey."""
    payload = {"service": "svc-q", "description": "explicit", "alert_id": "ignored"}
    alert = parse_alert(payload, source="generic")
    assert alert.service == "svc-q"


def test_parse_alert_garbage_payload_raises() -> None:
    with pytest.raises(UnknownPayloadError):
        parse_alert({"random": "stuff"})
