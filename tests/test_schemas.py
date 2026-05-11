"""Pydantic schema contracts — these are the structural gates the LLM must obey."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sre_agent.schemas import (
    AlertIn,
    DeploysEvidence,
    EvidenceResult,
    Hypothesis,
    HypothesisList,
    LogsEvidence,
    MetricSnapshot,
    MetricsEvidence,
    RemediationAction,
    RemediationPlan,
    RemediationRisk,
    Severity,
)


def test_alert_in_immutable_and_validates():
    a = AlertIn(
        service="checkout-api",
        severity=Severity.SEV_1,
        description="p99 3s",
        started_at=datetime.now(timezone.utc),
    )
    with pytest.raises(Exception):
        a.service = "boom"  # frozen=True


def test_severity_must_be_known():
    with pytest.raises(Exception):
        AlertIn(
            service="x",
            severity="SEV-99",  # type: ignore[arg-type]
            description="x",
            started_at=datetime.now(timezone.utc),
        )


def test_logs_evidence_negative_hits_rejected():
    with pytest.raises(Exception):
        LogsEvidence(result=EvidenceResult.FOUND, hits=-1, interpretation="bad")


def test_hypothesis_confidence_bounded():
    with pytest.raises(Exception):
        Hypothesis(title="x", detail="x", confidence=1.5)


def test_hypothesis_evidence_dedupes():
    h = Hypothesis(
        title="t",
        detail="d",
        confidence=0.8,
        supporting_evidence=["logs", "logs", "metrics"],
    )
    assert h.supporting_evidence == ["logs", "metrics"]


def test_hypothesis_list_top_picks_max_confidence():
    hl = HypothesisList(
        hypotheses=[
            Hypothesis(title="a", detail="a", confidence=0.3),
            Hypothesis(title="b", detail="b", confidence=0.9),
            Hypothesis(title="c", detail="c", confidence=0.5),
        ]
    )
    assert hl.top.title == "b"


def test_hypothesis_list_must_have_at_least_one():
    with pytest.raises(Exception):
        HypothesisList(hypotheses=[])


def test_remediation_action_requires_reversal():
    """A remediation without a reversal path should fail validation."""
    with pytest.raises(Exception):
        RemediationAction(
            title="restart",
            command="kubectl rollout restart deploy/x",
            why="…",
            expected_effect="…",
            risk=RemediationRisk.MEDIUM,
            # reversal missing!
        )  # type: ignore[call-arg]


def test_metric_snapshot_is_spike_flag():
    normal = MetricSnapshot(name="cpu", baseline=1, peak=2, verdict="NORMAL")
    spike = MetricSnapshot(name="cpu", baseline=1, peak=200, verdict="SPIKE (200x)")
    assert not normal.is_spike
    assert spike.is_spike


def test_metrics_evidence_round_trips_to_json():
    ev = MetricsEvidence(
        result=EvidenceResult.FOUND,
        interpretation="ok",
        metrics=[MetricSnapshot(name="cpu", baseline=1, peak=2, verdict="SPIKE (2x)")],
    )
    raw = ev.model_dump_json()
    loaded = MetricsEvidence.model_validate_json(raw)
    assert loaded.metrics[0].name == "cpu"


def test_remediation_plan_caps_actions_and_do_not_do():
    """We don't allow Suggester to spam unlimited actions."""
    with pytest.raises(Exception):
        RemediationPlan(
            actions=[
                RemediationAction(
                    title=f"a{i}",
                    command="echo",
                    why="w",
                    expected_effect="e",
                    reversal="r",
                    risk=RemediationRisk.LOW,
                )
                for i in range(6)  # > 5
            ]
        )


def test_deploys_evidence_empty_is_no_signal_ok():
    ev = DeploysEvidence(
        result=EvidenceResult.NO_SIGNAL,
        interpretation="No deploys.",
    )
    assert ev.deploys == []
    assert ev.config_changes == []
