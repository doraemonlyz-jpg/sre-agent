"""
Tests for sre_agent.calibration -- L6.3 confidence calibration.

Coverage:
  * Scalar metrics (ECE, Brier) on hand-computed cases.
  * Reliability bucketing edge cases (empty bins, p=1.0 edge,
    out-of-range rejection).
  * PAV isotonic fit:
      - Identity on already-calibrated data.
      - Monotonic output.
      - Reduces ECE on miscalibrated training data.
      - apply() interpolation + clamping.
  * Save/load JSON roundtrip + missing-file = identity fallback.
  * Bridge from on-disk feedback corpus.
  * Verdict-to-outcome mapping (no_signal and timeout excluded).
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pytest

from sre_agent.calibration import (
    CalibrationReport,
    IsotonicCalibrator,
    ReliabilityBin,
    _verdict_to_outcome,
    brier_score,
    expected_calibration_error,
    gather_pairs_from_feedback,
    reliability_diagram,
    render_markdown,
    summarize,
)


# ──────────────────────────────────────────────────────────────────────────
# Scalar metrics
# ──────────────────────────────────────────────────────────────────────────


class TestReliabilityDiagram:
    def test_empty_input_returns_empty_bins(self):
        bins = reliability_diagram([], n_bins=5)
        assert len(bins) == 5
        assert all(b.count == 0 for b in bins)

    def test_bin_widths_and_edges(self):
        pairs = [(0.05, 1), (0.55, 0), (0.99, 1), (1.0, 1)]
        bins = reliability_diagram(pairs, n_bins=10)
        # p=0.05 in bin 0, 0.55 in bin 5, 0.99 in bin 9, 1.0 in bin 9 (closed-right edge)
        assert bins[0].count == 1
        assert bins[5].count == 1
        assert bins[9].count == 2  # both 0.99 and 1.0

    def test_mean_pred_and_frac_correct(self):
        pairs = [(0.10, 1), (0.20, 0), (0.15, 1)]  # all in bin 0..0.1 except 0.20
        bins = reliability_diagram(pairs, n_bins=10)
        b0 = bins[1]  # 0.10 -> idx 1, 0.15 -> idx 1, 0.20 -> idx 2
        assert b0.count == 2
        assert b0.mean_pred == pytest.approx((0.10 + 0.15) / 2)
        assert b0.frac_correct == pytest.approx(1.0)
        b2 = bins[2]
        assert b2.count == 1
        assert b2.frac_correct == 0.0

    def test_rejects_oob_prob(self):
        with pytest.raises(ValueError, match="out of"):
            reliability_diagram([(1.1, 1)], n_bins=5)
        with pytest.raises(ValueError, match="out of"):
            reliability_diagram([(-0.1, 0)], n_bins=5)

    def test_rejects_non_binary_outcome(self):
        with pytest.raises(ValueError, match="must be 0 or 1"):
            reliability_diagram([(0.5, 2)], n_bins=5)

    def test_too_few_bins(self):
        with pytest.raises(ValueError, match="at least 2"):
            reliability_diagram([(0.5, 1)], n_bins=1)


class TestECE:
    def test_perfectly_calibrated_has_zero_ece(self):
        # 100 pairs at 0.5 with 50% correct -> bin mean == frac_correct
        pairs = [(0.5, 1) for _ in range(50)] + [(0.5, 0) for _ in range(50)]
        ece = expected_calibration_error(reliability_diagram(pairs, n_bins=10))
        assert ece == pytest.approx(0.0)

    def test_systematically_overconfident_has_positive_ece(self):
        # Says 0.9, only 50% right -> 0.4 gap, all weight in one bin
        pairs = [(0.9, 1) for _ in range(50)] + [(0.9, 0) for _ in range(50)]
        ece = expected_calibration_error(reliability_diagram(pairs, n_bins=10))
        assert ece == pytest.approx(0.4)

    def test_empty_bins_contribute_nothing(self):
        pairs = [(0.5, 1) for _ in range(10)]  # one bin only
        bins = reliability_diagram(pairs, n_bins=10)
        empty = [b for b in bins if b.count == 0]
        assert len(empty) == 9  # 9 empty bins, ECE only counts the populated one
        ece = expected_calibration_error(bins)
        assert ece == pytest.approx(0.5)  # said 0.5, right 100% of the time


class TestBrier:
    def test_perfect_prediction_zero_brier(self):
        assert brier_score([(1.0, 1), (0.0, 0)]) == pytest.approx(0.0)

    def test_worst_case_brier_is_one(self):
        assert brier_score([(1.0, 0), (0.0, 1)]) == pytest.approx(1.0)

    def test_half_predictions(self):
        # All predictions at 0.5, outcome irrelevant: brier = (0.5)^2 = 0.25
        pairs = [(0.5, 1) for _ in range(10)] + [(0.5, 0) for _ in range(10)]
        assert brier_score(pairs) == pytest.approx(0.25)

    def test_empty_brier_is_zero(self):
        assert brier_score([]) == 0.0


# ──────────────────────────────────────────────────────────────────────────
# Isotonic calibrator (PAV)
# ──────────────────────────────────────────────────────────────────────────


class TestIsotonicCalibratorBasics:
    def test_identity_default(self):
        cal = IsotonicCalibrator.identity()
        assert cal.is_identity
        assert cal.apply(0.0) == 0.0
        assert cal.apply(0.4) == 0.4
        assert cal.apply(1.0) == 1.0

    def test_apply_rejects_oob(self):
        cal = IsotonicCalibrator.identity()
        with pytest.raises(ValueError):
            cal.apply(1.5)
        with pytest.raises(ValueError):
            cal.apply(-0.1)

    def test_fit_below_min_pairs_returns_identity(self):
        pairs = [(0.5, 1)] * 30
        cal = IsotonicCalibrator.fit(pairs, min_pairs=100)
        assert cal.is_identity
        assert cal.n_train == 30


class TestIsotonicCalibratorPAV:
    """The PAV core: monotonicity + ECE reduction."""

    def _make_overconfident(self, n: int = 1000, rng_seed: int = 7) -> list[tuple[float, int]]:
        """
        Synthesise an overconfident corpus: model says 0.7-1.0, actual
        accuracy 0.5-0.7. The calibrator should learn to map raw -> lower.
        """
        rng = random.Random(rng_seed)
        pairs: list[tuple[float, int]] = []
        for _ in range(n):
            raw = rng.uniform(0.7, 1.0)
            true_p = 0.5 + (raw - 0.7) * 0.667  # roughly maps 0.7->0.5, 1.0->0.7
            outcome = 1 if rng.random() < true_p else 0
            pairs.append((raw, outcome))
        return pairs

    def test_fit_produces_monotonic_breakpoints(self):
        pairs = self._make_overconfident(n=500)
        cal = IsotonicCalibrator.fit(pairs, min_pairs=100)
        assert not cal.is_identity
        ys = [y for _, y in cal.breakpoints]
        xs = [x for x, _ in cal.breakpoints]
        for i in range(1, len(xs)):
            assert xs[i] >= xs[i - 1] - 1e-9
        for i in range(1, len(ys)):
            assert ys[i] >= ys[i - 1] - 1e-9

    def test_apply_is_monotonic(self):
        pairs = self._make_overconfident(n=500)
        cal = IsotonicCalibrator.fit(pairs, min_pairs=100)
        probs = [i / 100 for i in range(0, 101)]
        outputs = [cal.apply(p) for p in probs]
        for i in range(1, len(outputs)):
            assert outputs[i] >= outputs[i - 1] - 1e-9
            assert 0.0 <= outputs[i] <= 1.0

    def test_apply_reduces_ece_on_overconfident_data(self):
        pairs = self._make_overconfident(n=2000)
        cal = IsotonicCalibrator.fit(pairs, min_pairs=100)
        ece_before = expected_calibration_error(reliability_diagram(pairs))
        ece_after = expected_calibration_error(
            reliability_diagram([(cal.apply(p), y) for p, y in pairs])
        )
        assert ece_after < ece_before, (
            f"calibrator did not reduce ECE: {ece_before:.4f} -> {ece_after:.4f}"
        )
        # And the reported fit metrics should agree with our recompute
        assert cal.fit_ece_after == pytest.approx(ece_after, abs=1e-6)
        assert cal.fit_ece_before == pytest.approx(ece_before, abs=1e-6)

    def test_already_calibrated_data_stays_near_identity(self):
        """Data that's already calibrated should NOT get mangled."""
        rng = random.Random(13)
        pairs = []
        for _ in range(2000):
            p = round(rng.uniform(0.05, 0.95), 2)
            outcome = 1 if rng.random() < p else 0
            pairs.append((p, outcome))
        cal = IsotonicCalibrator.fit(pairs, min_pairs=100)
        # ECE should already be tiny; after fit it should still be tiny.
        assert cal.fit_ece_after < 0.05

    def test_apply_clamps_outside_training_range(self):
        # Train on only [0.7, 1.0]; apply outside should clamp to endpoints.
        pairs = [(0.7 + 0.001 * i, i % 2) for i in range(300)]
        cal = IsotonicCalibrator.fit(pairs, min_pairs=100)
        if cal.is_identity:
            pytest.skip("degenerate fit; not exercising clamp")
        assert cal.apply(0.1) == cal.apply(cal.breakpoints[0][0] - 0.01)
        assert cal.apply(0.99) == pytest.approx(cal.apply(0.95), abs=1e-3)

    def test_pav_collapses_pure_violation(self):
        """Trivial test that PAV pools when raw input order disagrees with outcome."""
        # Build a corpus where higher raw conf has LOWER actual outcome.
        pairs: list[tuple[float, int]] = []
        for _ in range(200):
            pairs.append((0.2, 1))  # low raw, always right
        for _ in range(200):
            pairs.append((0.8, 0))  # high raw, always wrong
        cal = IsotonicCalibrator.fit(pairs, min_pairs=100)
        # PAV should collapse both groups into a single pooled output:
        # avg outcome = 0.5, so apply should give ~0.5 for any input in range.
        assert cal.apply(0.2) == pytest.approx(0.5, abs=1e-3)
        assert cal.apply(0.8) == pytest.approx(0.5, abs=1e-3)


class TestIsotonicCalibratorIO:
    def test_roundtrip(self, tmp_path: Path):
        # Save/load rounds breakpoints to 6 dp for human-readable JSON;
        # we assert closeness rather than bit-identity, plus apply()
        # equivalence to a reasonable tolerance, which is what callers
        # actually care about.
        rng = random.Random(99)
        pairs = [(rng.uniform(0.6, 0.95), 1 if rng.random() < 0.6 else 0) for _ in range(500)]
        cal = IsotonicCalibrator.fit(pairs, min_pairs=100)
        path = tmp_path / "calibrator.json"
        cal.save(path)
        cal2 = IsotonicCalibrator.load(path)
        assert cal2.is_identity == cal.is_identity
        assert cal2.n_train == cal.n_train
        assert len(cal2.breakpoints) == len(cal.breakpoints)
        for (x1, y1), (x2, y2) in zip(cal.breakpoints, cal2.breakpoints):
            assert math.isclose(x1, x2, abs_tol=1e-5)
            assert math.isclose(y1, y2, abs_tol=1e-5)
        for p in [0.0, 0.25, 0.6, 0.85, 1.0]:
            assert cal.apply(p) == pytest.approx(cal2.apply(p), abs=1e-5)

    def test_load_missing_file_returns_identity(self, tmp_path: Path):
        cal = IsotonicCalibrator.load(tmp_path / "does-not-exist.json")
        assert cal.is_identity
        assert cal.apply(0.7) == 0.7

    def test_load_corrupt_file_returns_identity(self, tmp_path: Path):
        path = tmp_path / "corrupt.json"
        path.write_text("not json {{")
        cal = IsotonicCalibrator.load(path)
        assert cal.is_identity

    def test_save_atomic(self, tmp_path: Path):
        """Save shouldn't leave a half-written file under the final name."""
        path = tmp_path / "out.json"
        cal = IsotonicCalibrator.identity()
        cal.save(path)
        # No .tmp leftover, valid JSON at the final path
        assert path.is_file()
        assert json.loads(path.read_text())["is_identity"] is True
        assert not (tmp_path / "out.json.tmp").exists()


# ──────────────────────────────────────────────────────────────────────────
# Feedback -> pairs bridge
# ──────────────────────────────────────────────────────────────────────────


class TestVerdictToOutcome:
    def test_positives(self):
        assert _verdict_to_outcome("thumbs_up") == 1
        assert _verdict_to_outcome("correct") == 1

    def test_negatives(self):
        assert _verdict_to_outcome("thumbs_down") == 0
        assert _verdict_to_outcome("incorrect") == 0

    def test_abstentions_are_none(self):
        assert _verdict_to_outcome("no_signal") is None
        assert _verdict_to_outcome("timeout") is None
        assert _verdict_to_outcome("") is None


class TestGatherPairs:
    def _write_blob(self, dirp: Path, incident_id: str, records: list[dict]):
        blob = {"incident_id": incident_id, "records": records}
        (dirp / f"{incident_id}.json").write_text(json.dumps(blob))

    def test_extracts_only_with_confidence_and_binary_outcome(self, tmp_path: Path):
        self._write_blob(tmp_path, "i1", [
            {"verdict": "thumbs_up", "agent_confidence": 0.9},      # included
            {"verdict": "thumbs_down", "agent_confidence": 0.5},    # included
            {"verdict": "no_signal", "agent_confidence": 0.2},      # excluded: abstention
            {"verdict": "thumbs_up"},                               # excluded: no conf
            {"verdict": "thumbs_up", "agent_confidence": None},     # excluded: null conf
            {"verdict": "thumbs_up", "agent_confidence": 1.5},      # excluded: oob
            {"verdict": "thumbs_up", "agent_confidence": "high"},   # excluded: not a number
        ])
        pairs = gather_pairs_from_feedback(tmp_path)
        assert sorted(pairs) == [(0.5, 0), (0.9, 1)]

    def test_missing_dir_returns_empty(self, tmp_path: Path):
        assert gather_pairs_from_feedback(tmp_path / "missing") == []

    def test_corrupt_files_are_skipped(self, tmp_path: Path):
        (tmp_path / "ok.json").write_text(json.dumps({
            "incident_id": "ok",
            "records": [{"verdict": "thumbs_up", "agent_confidence": 0.7}],
        }))
        (tmp_path / "bad.json").write_text("not json")
        pairs = gather_pairs_from_feedback(tmp_path)
        assert pairs == [(0.7, 1)]


# ──────────────────────────────────────────────────────────────────────────
# Markdown rendering smoke
# ──────────────────────────────────────────────────────────────────────────


class TestMarkdownReport:
    def test_identity_report_says_no_fit(self):
        cal = IsotonicCalibrator.identity()
        report = summarize([(0.5, 1), (0.5, 0)], n_bins=10)
        md = render_markdown(report, calibrator=cal)
        assert "Calibration report" in md
        assert "No calibrator fitted" in md
        assert "Reliability diagram (before)" in md

    def test_fitted_report_shows_before_after(self):
        rng = random.Random(123)
        pairs = []
        for _ in range(800):
            raw = rng.uniform(0.7, 1.0)
            outcome = 1 if rng.random() < 0.5 else 0
            pairs.append((raw, outcome))
        cal = IsotonicCalibrator.fit(pairs, min_pairs=100)
        before = summarize(pairs)
        after = summarize([(cal.apply(p), y) for p, y in pairs])
        md = render_markdown(before, calibrator=cal, report_after=after, feedback_dir="/tmp/x")
        assert "Reliability diagram (before)" in md
        assert "Reliability diagram (after" in md
        assert "Fitted breakpoints" in md
        assert "raw=" in md
        assert "/tmp/x" in md


class TestSummarize:
    def test_n_pairs_and_keys_present(self):
        report = summarize([(0.5, 1), (0.5, 0)])
        assert isinstance(report, CalibrationReport)
        assert report.n_pairs == 2
        d = report.as_dict()
        assert {"n_pairs", "ece", "brier", "bins", "note"} <= d.keys()
        assert isinstance(d["bins"], list)


class TestReliabilityBinAsDict:
    def test_serialization(self):
        b = ReliabilityBin(low=0.2, high=0.3, count=5, mean_pred=0.25, frac_correct=0.4)
        d = b.as_dict()
        assert d["count"] == 5
        assert d["mean_pred"] == 0.25
        assert d["frac_correct"] == 0.4
