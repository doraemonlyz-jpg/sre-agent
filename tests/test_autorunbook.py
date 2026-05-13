"""
Tests for the auto-runbook drafter.

We're testing the boundary between "feedback corpus → reviewable
Markdown draft". The drafter's job is to be HONEST: don't surface
one-off rants as patterns, but don't silently drop a real signal
either.
"""

from __future__ import annotations

import pytest

from sre_agent.autorunbook import (
    alert_shape,
    draft,
    gather_corrections,
)
from sre_agent.feedback import STORE as FEEDBACK_STORE
from sre_agent.feedback import make_record


@pytest.fixture(autouse=True)
def _isolated_feedback_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SRE_FEEDBACK_DIR", str(tmp_path / "feedback"))
    FEEDBACK_STORE.reset()
    yield
    FEEDBACK_STORE.reset()


# ──────────────────────────────────────────────────────────────────────────
# alert_shape -- clustering primitive
# ──────────────────────────────────────────────────────────────────────────


def test_alert_shape_strips_numbers():
    """Two alerts with different numbers but the same prose should
    bucket together -- otherwise every alert is a singleton."""
    a = alert_shape("p99 latency 1500ms spiking, error rate 12%")
    b = alert_shape("p99 latency 4000ms spiking, error rate 8%")
    assert a == b


def test_alert_shape_normalises_case():
    a = alert_shape("OOM kill imminent on user-profile")
    b = alert_shape("oom kill imminent on user-profile")
    assert a == b


def test_alert_shape_empty_input():
    assert alert_shape(None) == "unknown"
    assert alert_shape("") == "unknown"


def test_alert_shape_drops_stop_words():
    """Test the actual word filtering, not numeric."""
    s = alert_shape("rate is on the high side after deploy")
    # 'is', 'on', 'the', 'after' all dropped; 'rate', 'high', 'side',
    # 'deploy' kept (first 4).
    assert "is" not in s.split("-")
    assert "the" not in s.split("-")


# ──────────────────────────────────────────────────────────────────────────
# gather_corrections -- the filter
# ──────────────────────────────────────────────────────────────────────────


def test_gather_skips_thumbs_up_records():
    """Only thumbs_down / incorrect produce learnable corrections."""
    records = [
        {"verdict": "thumbs_up", "correct_root_cause": "irrelevant"},
        {"verdict": "thumbs_down", "correct_root_cause": "real cause"},
    ]
    out = gather_corrections(records)
    assert len(out) == 1
    assert out[0].oncall_said == "real cause"


def test_gather_skips_records_without_root_cause():
    """A bare thumbs_down with no correction is noise, not signal."""
    records = [
        {"verdict": "thumbs_down", "correct_root_cause": None},
        {"verdict": "thumbs_down", "correct_root_cause": ""},
        {"verdict": "thumbs_down", "correct_root_cause": "the real one"},
    ]
    out = gather_corrections(records)
    assert len(out) == 1
    assert out[0].oncall_said == "the real one"


# ──────────────────────────────────────────────────────────────────────────
# draft() -- full pipeline against the store
# ──────────────────────────────────────────────────────────────────────────


def _seed_correction(
    *,
    incident_id: str,
    service: str,
    description: str,
    correction: str,
    submitter: str = "alice",
    remediation: str | None = None,
    agent_root_cause: str | None = None,
):
    """Helper: simulate a real feedback append with alert snapshot."""
    rec = make_record(
        verdict="thumbs_down",
        submitter=submitter,
        correct_root_cause=correction,
        correct_remediation=remediation,
        agent_root_cause=agent_root_cause,
    )
    FEEDBACK_STORE.append(
        incident_id,
        rec,
        alert={"service": service, "description": description},
    )


def test_draft_suppresses_singletons():
    """One correction → not yet a pattern. Suppress."""
    _seed_correction(
        incident_id="i1",
        service="checkout-api",
        description="p99 latency 1500ms spiking, error rate 12%",
        correction="downstream issue, not us",
    )
    report = draft(min_occurrences=2)
    assert report.clusters == []
    assert report.skipped_below_threshold == 1


def test_draft_promotes_repeating_patterns():
    """3 corrections on the same (service, shape) → emit one cluster."""
    for i in range(3):
        _seed_correction(
            incident_id=f"i{i}",
            service="checkout-api",
            description=f"p99 latency {1500 + i*100}ms spiking",
            correction="downstream payment-gateway timeout",
            submitter=f"oncall-{i}",
            agent_root_cause="Redis pool exhaustion",
        )
    report = draft(min_occurrences=2)
    assert len(report.clusters) == 1
    c = report.clusters[0]
    assert c.service == "checkout-api"
    assert c.occurrences == 3
    assert len(c.distinct_submitters) == 3


def test_draft_renders_agent_vs_oncall_pairing():
    """The whole point of `agent_root_cause` is so the PR reviewer
    sees the contradiction inline. Render it."""
    for i in range(3):
        _seed_correction(
            incident_id=f"i{i}",
            service="payments-gateway",
            description="5xx rate sustained after deploy",
            correction="feature flag misconfigured, not deploy",
            agent_root_cause="bad deploy",
        )
    report = draft(min_occurrences=2)
    md = report.to_markdown()
    assert "bad deploy" in md
    assert "feature flag misconfigured" in md


def test_draft_separates_by_service():
    """Same shape on different services → distinct clusters. They
    might share a root cause, but the runbook entries should be
    service-specific."""
    for i in range(2):
        _seed_correction(
            incident_id=f"a{i}",
            service="checkout-api",
            description="p99 latency spiking",
            correction="downstream slow",
        )
    for i in range(2):
        _seed_correction(
            incident_id=f"b{i}",
            service="search-suggest",
            description="p99 latency spiking",
            correction="reindex job interfering",
        )
    report = draft(min_occurrences=2)
    services = sorted(c.service for c in report.clusters)
    assert services == ["checkout-api", "search-suggest"]


def test_draft_picks_modal_remediation():
    """When multiple corrections share a remediation, the "suggested
    action" -- the prose block at the bottom of each cluster, intended
    as the take-away for the runbook -- should be the most common one,
    not whichever was last in. The per-pair detail list above is
    allowed to show variation; we only assert on the recommendation."""
    for _ in range(4):
        _seed_correction(
            incident_id=f"x{_}",
            service="cdn-router",
            description="5xx after deploy",
            correction="rollback the bad PR",
            remediation="rollback PR #12345",
        )
    _seed_correction(
        incident_id="x99",
        service="cdn-router",
        description="5xx after deploy",
        correction="rollback the bad PR",
        remediation="(noise -- not the real fix)",
    )
    report = draft(min_occurrences=2)
    md = report.to_markdown()
    # Carve out the "Suggested runbook entry" block.
    marker = "### Suggested runbook entry"
    assert marker in md
    suggested = md.split(marker, 1)[1]
    assert "rollback PR #12345" in suggested
    assert "(noise" not in suggested


def test_draft_renders_empty_with_helpful_text():
    """No data is a valid state. Don't crash, and tell the reader
    why there's nothing to read."""
    report = draft(min_occurrences=2)
    md = report.to_markdown()
    assert "No clusters above threshold" in md
