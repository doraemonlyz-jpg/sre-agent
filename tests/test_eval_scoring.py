"""Unit tests for the eval harness scoring functions (pure, no LangGraph)."""

from __future__ import annotations

from tests.eval.scoring import ExpectedOutcome, score_case

# Sentinel for "argument not provided" so a caller can deliberately pass [].
_UNSET = object()


def _make_report(
    *,
    phase: str = "diagnosed",
    supporting=_UNSET,
    title: str = "Redis connection pool exhausted after deploy",
    detail: str = "deploy abc123 changed pool size; restart fixes it",
    confidence: float = 0.78,
    runbook_paths: list[str] | None = None,
    action_titles: list[str] | None = None,
) -> dict:
    if supporting is _UNSET:
        supporting = ["logs", "deploys"]
    return {
        "phase": phase,
        "findings": {
            "runbooks": {
                "hits": [{"path": p, "title": p, "score": 0.5} for p in (runbook_paths or [])]
            }
        },
        "hypothesis": {
            "title": title,
            "detail": detail,
            "confidence": confidence,
            "supporting_evidence": supporting,
        },
        "remediation": {
            "actions": [{"title": t, "command": "x"} for t in (action_titles or [])]
        },
    }


class TestScoreCase:
    def test_all_checks_pass(self):
        rep = _make_report(
            supporting=["logs", "deploys", "runbooks"],
            runbook_paths=["runbooks/checkout-api.md"],
            action_titles=["Rollback deploy abc123"],
        )
        exp = ExpectedOutcome(
            phase=["diagnosed"],
            must_cite_evidence=["logs", "deploys"],
            hypothesis_keywords_any=["redis", "pool"],
            runbook_path_contains="checkout-api",
            confidence_range=(0.5, 1.0),
            remediation_action_titles_any=["rollback", "revert"],
        )
        result = score_case("c", exp, rep, threshold=0.8)
        assert result.passed
        assert result.score == 1.0
        assert all(ok for _, ok, _ in result.checks)

    def test_phase_mismatch_fails(self):
        rep = _make_report(phase="no_signal")
        exp = ExpectedOutcome(phase=["diagnosed"])
        result = score_case("c", exp, rep)
        assert not result.passed
        assert result.score == 0.0

    def test_must_not_phase(self):
        rep = _make_report(phase="failed")
        exp = ExpectedOutcome(must_not_phase=["failed"])
        result = score_case("c", exp, rep)
        assert not result.passed

    def test_missing_evidence_citation(self):
        rep = _make_report(supporting=["logs"])  # only logs, no deploys
        exp = ExpectedOutcome(must_cite_evidence=["logs", "deploys"])
        result = score_case("c", exp, rep)
        assert not result.passed

    def test_keyword_partial_match_passes(self):
        # "pool" matches even though we asked for "redis OR pool"
        rep = _make_report(title="Connection pool exhausted", detail="N/A")
        exp = ExpectedOutcome(hypothesis_keywords_any=["redis", "pool"])
        result = score_case("c", exp, rep)
        assert result.passed

    def test_confidence_out_of_range(self):
        rep = _make_report(confidence=0.10)
        exp = ExpectedOutcome(confidence_range=(0.5, 1.0))
        result = score_case("c", exp, rep)
        assert not result.passed

    def test_runbook_match_ci(self):
        rep = _make_report(runbook_paths=["runbooks/Checkout-API.md"])
        exp = ExpectedOutcome(runbook_path_contains="checkout-api")
        result = score_case("c", exp, rep)
        assert result.passed

    def test_partial_score_below_threshold(self):
        # 1/2 checks pass → score 0.5 → fails default threshold 0.8
        rep = _make_report(phase="diagnosed", supporting=[])
        exp = ExpectedOutcome(
            phase=["diagnosed"],
            must_cite_evidence=["logs"],  # missing
        )
        result = score_case("c", exp, rep, threshold=0.8)
        assert not result.passed
        assert result.score == 0.5

    def test_partial_score_above_threshold(self):
        # 1/2 checks pass → score 0.5 → passes threshold 0.4
        rep = _make_report(phase="diagnosed", supporting=[])
        exp = ExpectedOutcome(
            phase=["diagnosed"],
            must_cite_evidence=["logs"],
        )
        result = score_case("c", exp, rep, threshold=0.4)
        assert result.passed

    def test_empty_expected_scores_zero(self):
        # No checks defined — that's a usage error; we score 0 to make it loud.
        result = score_case("c", ExpectedOutcome(), _make_report())
        assert result.score == 0.0
        assert not result.passed
