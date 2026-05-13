"""
Tests for the L6.1 winner-promotion analyzer.

We test the analyzer's PRINCIPLES, not its current numbers:
  * On thin evidence, hold.
  * On strong evidence + meaningful effect, promote.
  * Never promote if the candidate is the existing baseline.
  * Stat functions are correct on known inputs.

Edge cases get explicit tests because they're the ones that fire in
prod (zero data, single-arm, ties).
"""

from __future__ import annotations

import pytest

from sre_agent.winner import (
    aggregate_feedback,
    analyze,
    two_prop_z,
    wilson_interval,
)

# ──────────────────────────────────────────────────────────────────────────
# Stat helpers
# ──────────────────────────────────────────────────────────────────────────


def test_wilson_interval_n_zero_is_full_range():
    """No data → no information. Don't be wrong here, it'd corrupt
    every report."""
    low, high = wilson_interval(0, 0)
    assert (low, high) == (0.0, 1.0)


def test_wilson_interval_full_positive():
    low, high = wilson_interval(100, 100)
    # Upper bound is 1 (capped), lower should be safely under 1.
    assert high == pytest.approx(1.0)
    assert low < 1.0


def test_wilson_interval_known_value():
    """Known shape: 50/100 should be centred around 0.5 with a narrow
    CI compared to n=10."""
    low_big, high_big = wilson_interval(50, 100)
    low_small, high_small = wilson_interval(5, 10)
    assert (high_big - low_big) < (high_small - low_small)
    # Sanity: contains the point estimate.
    assert low_big <= 0.5 <= high_big


def test_two_prop_z_returns_zero_for_identical_groups():
    z, p = two_prop_z(50, 100, 50, 100)
    assert z == pytest.approx(0.0)
    assert p == pytest.approx(1.0)


def test_two_prop_z_large_difference_low_p():
    """Strong effect on big-N must be detected."""
    z, p = two_prop_z(900, 1000, 500, 1000)
    assert abs(z) > 5
    assert p < 1e-6


def test_two_prop_z_empty_arm_returns_neutral():
    """We never make claims about absent data."""
    z, p = two_prop_z(10, 100, 0, 0)
    assert z == 0.0
    assert p == 1.0


# ──────────────────────────────────────────────────────────────────────────
# Aggregation
# ──────────────────────────────────────────────────────────────────────────


def test_aggregate_groups_by_agent_then_sha():
    records = [
        {"verdict": "thumbs_up", "prompt_shas_seen": {"hyp": "AAA"}},
        {"verdict": "thumbs_down", "prompt_shas_seen": {"hyp": "AAA"}},
        {"verdict": "correct", "prompt_shas_seen": {"hyp": "BBB"}},
    ]
    out = aggregate_feedback(records)
    assert out["hyp"]["AAA"] == [2, 1]
    assert out["hyp"]["BBB"] == [1, 1]


def test_aggregate_ignores_records_without_shas():
    records = [
        {"verdict": "thumbs_up", "prompt_shas_seen": {}},
        {"verdict": "thumbs_up"},
        {"verdict": "thumbs_up", "prompt_shas_seen": {"hyp": "AAA"}},
    ]
    out = aggregate_feedback(records)
    assert out["hyp"]["AAA"] == [1, 1]


def test_aggregate_correct_counts_as_positive():
    """`correct` is the strongest signal -- must count as positive."""
    records = [
        {"verdict": "correct", "prompt_shas_seen": {"hyp": "X"}},
        {"verdict": "thumbs_up", "prompt_shas_seen": {"hyp": "X"}},
        {"verdict": "thumbs_down", "prompt_shas_seen": {"hyp": "X"}},
        {"verdict": "incorrect", "prompt_shas_seen": {"hyp": "X"}},
    ]
    out = aggregate_feedback(records)
    assert out["hyp"]["X"] == [4, 2]  # 4 total, 2 positives


# ──────────────────────────────────────────────────────────────────────────
# End-to-end analyze()
# ──────────────────────────────────────────────────────────────────────────


def _records(agent: str, sha: str, n: int, pos: int) -> list[dict]:
    """Build n synthetic records with `pos` positives, all using the
    given (agent, sha) pair."""
    out = []
    for i in range(n):
        verdict = "thumbs_up" if i < pos else "thumbs_down"
        out.append({"verdict": verdict, "prompt_shas_seen": {agent: sha}})
    return out


def test_analyze_promotes_strong_winner():
    """Variant beats baseline by 15pp at n=300 -- should promote."""
    records = []
    records += _records("hyp", "BASELINE", 300, 180)  # 60%
    records += _records("hyp", "VARIANT", 300, 225)   # 75%
    report = analyze(records=records, baselines={"hyp": "BASELINE"})
    d = report.decisions[0]
    assert d.verdict == "promote", d.reason
    assert d.winner_sha == "VARIANT"
    assert d.delta_pp > 10


def test_analyze_holds_when_below_significance():
    """1pp delta on n=100 each → high p-value → hold."""
    records = []
    records += _records("hyp", "BASELINE", 100, 60)
    records += _records("hyp", "VARIANT", 100, 61)
    report = analyze(records=records, baselines={"hyp": "BASELINE"})
    d = report.decisions[0]
    assert d.verdict == "hold"
    assert "below" in d.reason or "not significant" in d.reason


def test_analyze_holds_when_undersized():
    """Even huge delta on tiny n is uncertain. Hold."""
    records = []
    records += _records("hyp", "BASELINE", 10, 4)
    records += _records("hyp", "VARIANT", 10, 9)
    report = analyze(records=records, baselines={"hyp": "BASELINE"})
    d = report.decisions[0]
    assert d.verdict == "hold"
    assert "sample size" in d.reason


def test_analyze_holds_when_baseline_already_winning():
    """If the current baseline is the best, no promotion -- that's a
    common case and the reason text should reflect it."""
    records = []
    records += _records("hyp", "BASELINE", 500, 400)   # 80%
    records += _records("hyp", "VARIANT", 500, 200)    # 40% -- worse
    report = analyze(records=records, baselines={"hyp": "BASELINE"})
    d = report.decisions[0]
    assert d.verdict == "hold"
    assert d.winner_sha == "BASELINE"
    assert "baseline" in d.reason.lower()


def test_analyze_single_arm_holds():
    """With one prompt only there's no A/B running. Hold + clear reason."""
    records = _records("hyp", "BASELINE", 500, 400)
    report = analyze(records=records, baselines={"hyp": "BASELINE"})
    d = report.decisions[0]
    assert d.verdict == "hold"
    assert "only one" in d.reason


def test_analyze_thresholds_respected():
    """Effects must clear BOTH the min-delta and significance bars."""
    # Tiny but significant: 5000 records each, 1pp delta. Stat sig but
    # too small to be operationally meaningful.
    records = []
    records += _records("hyp", "BASELINE", 5000, 3000)  # 60.0%
    records += _records("hyp", "VARIANT", 5000, 3050)  # 61.0%
    report = analyze(records=records, baselines={"hyp": "BASELINE"},
                     min_delta_pp=3.0)
    d = report.decisions[0]
    assert d.verdict == "hold"
    assert "below min_delta_pp" in d.reason


def test_analyze_markdown_render_does_not_crash_on_empty():
    """No agents → empty report → still renders valid Markdown."""
    report = analyze(records=[], baselines={})
    md = report.to_markdown()
    assert "# Prompt A/B winner report" in md


def test_analyze_markdown_includes_winner_marker_for_promotes():
    """Promotion decisions should call out the winner explicitly in
    the table so the PR reviewer doesn't miss it."""
    records = []
    records += _records("hyp", "BASELINE", 300, 180)
    records += _records("hyp", "VARIANT", 300, 225)
    report = analyze(records=records, baselines={"hyp": "BASELINE"})
    md = report.to_markdown()
    assert "(winner)" in md
    assert "(baseline)" in md
    assert "promote" in md.lower()
