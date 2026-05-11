"""
SlackNotifier tests — dry-run + real-POST paths.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from sre_agent.notifications.slack import _SEV_EMOJI, SlackNotifier


@pytest.fixture
def diagnosed_incident() -> dict:
    """A representative dashboard-shape incident dict, post-diagnosis."""
    return {
        "id": "abc123",
        "alert": {
            "service": "checkout-api",
            "severity": "SEV-2",
            "description": "error rate spiking past 5%",
        },
        "started_at": 1_715_000_000_000,
        "diagnosis_ms": 4_200,
        "hypothesis": {
            "top": "Redis connection pool exhaustion after recent deploy",
            "confidence": 0.86,
        },
        "remediation": [
            {
                "title": "Roll back the last deploy",
                "command": "kubectl rollout undo deploy/checkout-api -n prod",
                "why": "deploy 10min before alert is the likely culprit",
                "risk": "MEDIUM",
            },
        ],
    }


# ──────────────────────────────────────────────────────────────────────────
# Dry run
# ──────────────────────────────────────────────────────────────────────────


def test_dry_run_when_no_webhook(diagnosed_incident: dict) -> None:
    """No webhook URL → dry-run mode, no network access, payload still built."""
    notifier = SlackNotifier(webhook_url=None)
    result = notifier.post_incident(diagnosed_incident)
    assert result.dry_run is True
    assert result.sent is False
    assert result.status is None
    # Payload always built so caller can copy it manually.
    assert "blocks" in result.payload
    assert any(b["type"] == "header" for b in result.payload["blocks"])
    # Preview is human-readable text.
    assert "checkout-api" in result.preview
    assert "Top hypothesis" in result.preview
    notifier.close()


def test_dry_run_explicit_override(diagnosed_incident: dict) -> None:
    """Webhook present but dry_run=True forces preview-only."""
    notifier = SlackNotifier(
        webhook_url="https://hooks.slack.com/services/T/X/Y",
        dry_run=True,
    )
    result = notifier.post_incident(diagnosed_incident)
    assert result.dry_run is True
    assert result.sent is False
    notifier.close()


def test_from_env_dry_run_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SRE_SLACK_DRY_RUN", raising=False)
    n = SlackNotifier.from_env()
    assert n.dry_run is True
    n.close()


def test_from_env_dry_run_explicit_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/X/Y")
    monkeypatch.setenv("SRE_SLACK_DRY_RUN", "true")
    n = SlackNotifier.from_env()
    assert n.dry_run is True
    n.close()


# ──────────────────────────────────────────────────────────────────────────
# Real POST
# ──────────────────────────────────────────────────────────────────────────


@respx.mock
def test_real_post_succeeds(diagnosed_incident: dict) -> None:
    route = respx.post("https://hooks.slack.com/services/T/X/Y").mock(
        return_value=httpx.Response(200, text="ok")
    )
    with SlackNotifier(
        webhook_url="https://hooks.slack.com/services/T/X/Y",
        dry_run=False,
    ) as notifier:
        result = notifier.post_incident(diagnosed_incident)

    assert route.called
    assert result.sent is True
    assert result.dry_run is False
    assert result.status == 200
    # Sanity-check the body we posted.
    sent_body = route.calls.last.request.read()
    assert b"checkout-api" in sent_body
    assert b"Top hypothesis" in sent_body


@respx.mock
def test_real_post_http_error_returns_result_no_raise(diagnosed_incident: dict) -> None:
    respx.post("https://hooks.slack.com/services/T/X/Y").mock(
        return_value=httpx.Response(500, text="oops")
    )
    with SlackNotifier(
        webhook_url="https://hooks.slack.com/services/T/X/Y",
        dry_run=False,
    ) as notifier:
        result = notifier.post_incident(diagnosed_incident)

    assert result.sent is False
    assert result.dry_run is False
    assert result.error is not None
    # Still includes preview/payload so we can fall back to surfacing in UI.
    assert "blocks" in result.payload


# ──────────────────────────────────────────────────────────────────────────
# Payload rendering
# ──────────────────────────────────────────────────────────────────────────


def test_severity_emoji_in_header(diagnosed_incident: dict) -> None:
    notifier = SlackNotifier(webhook_url=None)
    result = notifier.post_incident(diagnosed_incident)
    header_block = result.payload["blocks"][0]
    assert header_block["type"] == "header"
    assert _SEV_EMOJI["SEV-2"] in header_block["text"]["text"]


def test_payload_without_hypothesis(diagnosed_incident: dict) -> None:
    """Slack output still works for an undiagnosed-yet incident."""
    diagnosed_incident.pop("hypothesis")
    diagnosed_incident["remediation"] = []
    notifier = SlackNotifier(webhook_url=None)
    result = notifier.post_incident(diagnosed_incident)
    # No hypothesis block, but header + description + context still present.
    types = [b["type"] for b in result.payload["blocks"]]
    assert types[0] == "header"
    assert "section" in types
    assert "context" in types
