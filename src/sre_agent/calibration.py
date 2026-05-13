"""
sre_agent.calibration -- L6.3 confidence calibration.

Why this exists
---------------
When `hypothesis-gen` outputs ``confidence: 0.85`` on a hypothesis, we
want that number to *mean* 85%. In a well-calibrated system, of all
the times the agent says "85% sure", 85% of those calls turn out to be
right -- and on a reliability diagram the (predicted, actual) points
fall on the y=x line.

LLM-produced confidence is almost always uncalibrated out of the box.
Common failure modes:

  * **Over-confident**: model says 90% but is right only 65% of the
    time. Dangerous in incident response -- an oncall who trusts the
    number paces the wrong runbook.
  * **Under-confident**: model says 50% but is right 80% of the time.
    Wastes oncall attention on "let me double-check" loops.
  * **Non-monotonic**: model's 0.7 outputs are *less* often correct
    than its 0.5 outputs. Indicates the score is just noise.

What this module does
---------------------
A single-file calibration toolkit with no external dependencies (pure
stdlib: easier to ship into a CI image, no sklearn version pinning):

  * `reliability_diagram` -- bin (pred_prob, outcome) pairs and report
    the per-bin frequency. The output is a list of `ReliabilityBin`
    dataclasses ready for plotting or printing.
  * `expected_calibration_error` -- the classic ECE metric: weighted
    L1 distance between predicted and observed frequency, across bins.
  * `brier_score` -- mean squared error between prediction and outcome.
    Decomposes (mathematically) into calibration + refinement; we use
    the total as a single-number health check.
  * `IsotonicCalibrator` -- a Pool-Adjacent-Violators (PAV) implementation
    of isotonic regression that fits a *monotonic* mapping from raw
    probabilities to calibrated probabilities. Works well on the
    typical LLM miscalibration shape (over-confident-at-the-extremes).
  * `gather_pairs_from_feedback` -- bridges the on-disk feedback corpus
    (with `agent_confidence` + `verdict`) into the (pred, outcome) pair
    list the rest of the module consumes.

Why isotonic and not Platt scaling
----------------------------------
Platt scaling fits a 2-parameter logistic (a*x + b followed by sigmoid).
It assumes a specific S-curve shape that LLM miscalibration doesn't
always follow -- in particular, LLMs often have a flat region in the
middle and sharp curves at the ends. Isotonic regression is shape-free
(only requires monotonicity) so it adapts to whatever miscalibration
the corpus actually shows. The cost is that you need ~hundreds of
observations to fit it well; with N<100 we fall back to "identity"
and emit a warning.

Production wiring
-----------------
The fitted calibrator is a small JSON file (a step function: list of
(x, y) breakpoints). It's loaded at dashboard boot if present and
applied before surfacing any confidence number to oncall. It's safe to
ship missing: the loader returns an identity calibrator that's a no-op.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# ──────────────────────────────────────────────────────────────────────────
# Data types
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class ReliabilityBin:
    """One bin of a reliability diagram.

    `low`, `high` -- the half-open interval [low, high) the bin covers
                     in predicted-probability space.
    `count`       -- number of predictions in this bin.
    `mean_pred`   -- average predicted probability in the bin (the bin's
                     x-coordinate on the reliability diagram).
    `frac_correct`-- observed fraction of correct outcomes (the bin's
                     y-coordinate on the reliability diagram).

    A perfectly calibrated system has `frac_correct ≈ mean_pred` for
    every bin with non-trivial `count`.
    """

    low: float
    high: float
    count: int
    mean_pred: float
    frac_correct: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "low": round(self.low, 4),
            "high": round(self.high, 4),
            "count": self.count,
            "mean_pred": round(self.mean_pred, 4),
            "frac_correct": round(self.frac_correct, 4),
        }


@dataclass
class CalibrationReport:
    """Top-level summary of corpus calibration."""

    n_pairs: int
    ece: float
    brier: float
    bins: list[ReliabilityBin] = field(default_factory=list)
    note: str | None = None  # set when we had to short-circuit (e.g. N too small)

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_pairs": self.n_pairs,
            "ece": round(self.ece, 4),
            "brier": round(self.brier, 4),
            "bins": [b.as_dict() for b in self.bins],
            "note": self.note,
        }


# ──────────────────────────────────────────────────────────────────────────
# Reliability diagram + scalar metrics
# ──────────────────────────────────────────────────────────────────────────


def _validate(pairs: Iterable[tuple[float, int]]) -> list[tuple[float, int]]:
    out: list[tuple[float, int]] = []
    for p, y in pairs:
        if not (0.0 <= p <= 1.0):
            raise ValueError(f"predicted probability out of [0,1]: {p!r}")
        if y not in (0, 1):
            raise ValueError(f"outcome must be 0 or 1, got {y!r}")
        out.append((float(p), int(y)))
    return out


def reliability_diagram(
    pairs: Iterable[tuple[float, int]],
    *,
    n_bins: int = 10,
) -> list[ReliabilityBin]:
    """Bucket pairs into equal-width bins on [0, 1] and report per-bin stats.

    The last bin is closed on the right so a prediction of exactly 1.0
    lands in it instead of falling off the edge.
    """
    if n_bins < 2:
        raise ValueError("need at least 2 bins")
    pairs = _validate(pairs)
    width = 1.0 / n_bins
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, y in pairs:
        idx = int(p / width)
        if idx == n_bins:  # p == 1.0
            idx = n_bins - 1
        buckets[idx].append((p, y))

    out: list[ReliabilityBin] = []
    for i, bucket in enumerate(buckets):
        low = i * width
        high = low + width
        if not bucket:
            out.append(ReliabilityBin(
                low=low, high=high, count=0,
                mean_pred=0.0, frac_correct=0.0,
            ))
            continue
        mean_pred = sum(p for p, _ in bucket) / len(bucket)
        frac_correct = sum(y for _, y in bucket) / len(bucket)
        out.append(ReliabilityBin(
            low=low, high=high, count=len(bucket),
            mean_pred=mean_pred, frac_correct=frac_correct,
        ))
    return out


def expected_calibration_error(bins: list[ReliabilityBin]) -> float:
    """ECE: |mean_pred - frac_correct| weighted by bin count, summed."""
    total = sum(b.count for b in bins)
    if total == 0:
        return 0.0
    return sum(
        (b.count / total) * abs(b.mean_pred - b.frac_correct)
        for b in bins if b.count > 0
    )


def brier_score(pairs: Iterable[tuple[float, int]]) -> float:
    """Mean squared error of predicted probability vs outcome."""
    pairs = _validate(pairs)
    if not pairs:
        return 0.0
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def summarize(
    pairs: Iterable[tuple[float, int]],
    *,
    n_bins: int = 10,
) -> CalibrationReport:
    """Build a `CalibrationReport` from raw pairs."""
    pairs = _validate(pairs)
    bins = reliability_diagram(pairs, n_bins=n_bins)
    return CalibrationReport(
        n_pairs=len(pairs),
        ece=expected_calibration_error(bins),
        brier=brier_score(pairs),
        bins=bins,
    )


# ──────────────────────────────────────────────────────────────────────────
# Isotonic calibrator (Pool-Adjacent-Violators)
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class IsotonicCalibrator:
    """
    Monotonic piecewise-constant mapping from raw to calibrated probability.

    Built via the Pool-Adjacent-Violators (PAV) algorithm. We store the
    fit as a list of `(x, y)` breakpoints, x strictly non-decreasing,
    y non-decreasing. `apply(p)` does a linear interpolation between
    the two nearest breakpoints, clamped to [0, 1].

    Identity calibrator (no breakpoints) is the safe default: any
    consumer that loads it as a no-op is correct.
    """

    breakpoints: list[tuple[float, float]] = field(default_factory=list)
    n_train: int = 0
    fit_ece_before: float = 0.0
    fit_ece_after: float = 0.0
    fit_brier_before: float = 0.0
    fit_brier_after: float = 0.0
    is_identity: bool = True

    # ── classmethods ─────────────────────────────────────────────────

    @classmethod
    def identity(cls) -> "IsotonicCalibrator":
        return cls()

    @classmethod
    def fit(
        cls,
        pairs: Iterable[tuple[float, int]],
        *,
        min_pairs: int = 100,
        n_bins: int = 10,
    ) -> "IsotonicCalibrator":
        """
        Fit an isotonic calibrator on (predicted_prob, outcome) pairs.

        If fewer than `min_pairs` pairs are provided we fall back to the
        identity calibrator. The threshold guards against badly fit
        step-functions on tiny corpora -- a 30-point fit will gladly
        memorise noise and make calibration *worse* in expectation.
        """
        pairs = _validate(pairs)
        if len(pairs) < min_pairs:
            cal = cls.identity()
            cal.n_train = len(pairs)
            if pairs:
                cal.fit_brier_before = brier_score(pairs)
                cal.fit_brier_after = cal.fit_brier_before
                bins_before = reliability_diagram(pairs, n_bins=n_bins)
                cal.fit_ece_before = expected_calibration_error(bins_before)
                cal.fit_ece_after = cal.fit_ece_before
            return cal

        # Sort by raw prediction so PAV can sweep in one pass.
        sorted_pairs = sorted(pairs, key=lambda t: t[0])
        xs = [p for p, _ in sorted_pairs]
        ys = [float(y) for _, y in sorted_pairs]

        # PAV: greedy left-to-right, merging blocks while the running
        # mean of the merged block violates monotonicity.
        # Each entry: (sum_of_ys, count, x_low_index, x_high_index).
        blocks: list[list[float]] = [[y, 1, i, i] for i, y in enumerate(ys)]
        i = 0
        while i + 1 < len(blocks):
            mean_i = blocks[i][0] / blocks[i][1]
            mean_next = blocks[i + 1][0] / blocks[i + 1][1]
            if mean_i > mean_next:
                # Merge i and i+1, then back up to recheck against i-1.
                merged_sum = blocks[i][0] + blocks[i + 1][0]
                merged_count = blocks[i][1] + blocks[i + 1][1]
                merged_lo = blocks[i][2]
                merged_hi = blocks[i + 1][3]
                blocks[i] = [merged_sum, merged_count, merged_lo, merged_hi]
                blocks.pop(i + 1)
                if i > 0:
                    i -= 1
            else:
                i += 1

        # Materialise breakpoints: one per block, x = mean of the raw
        # predictions in the block, y = mean of the outcomes (which is
        # the calibrated probability for that raw range).
        bps: list[tuple[float, float]] = []
        for s, c, lo, hi in blocks:
            x_mean = sum(xs[lo:hi + 1]) / (hi - lo + 1)
            y_mean = s / c
            bps.append((x_mean, y_mean))

        # Sort + dedupe x: in pathological inputs (many ties) we might
        # produce blocks with identical x_mean; keep the last y for
        # those (PAV-merged blocks already pool y correctly).
        bps_sorted: list[tuple[float, float]] = []
        for x, y in bps:
            if bps_sorted and math.isclose(bps_sorted[-1][0], x):
                bps_sorted[-1] = (x, y)
            else:
                bps_sorted.append((x, y))

        cal = cls(
            breakpoints=bps_sorted,
            n_train=len(pairs),
            is_identity=False,
        )

        # Diagnostics: how much did we move the needle on the training set?
        # (Test-set ECE is what matters in prod but the dashboard wants
        # a fit-quality readout too.)
        bins_before = reliability_diagram(pairs, n_bins=n_bins)
        bins_after = reliability_diagram(
            [(cal.apply(p), y) for p, y in pairs], n_bins=n_bins,
        )
        cal.fit_ece_before = expected_calibration_error(bins_before)
        cal.fit_ece_after = expected_calibration_error(bins_after)
        cal.fit_brier_before = brier_score(pairs)
        cal.fit_brier_after = brier_score(
            [(cal.apply(p), y) for p, y in pairs]
        )

        return cal

    @classmethod
    def from_dict(cls, blob: dict[str, Any]) -> "IsotonicCalibrator":
        bps_raw = blob.get("breakpoints") or []
        bps = [(float(x), float(y)) for x, y in bps_raw]
        return cls(
            breakpoints=bps,
            n_train=int(blob.get("n_train", 0)),
            fit_ece_before=float(blob.get("fit_ece_before", 0.0)),
            fit_ece_after=float(blob.get("fit_ece_after", 0.0)),
            fit_brier_before=float(blob.get("fit_brier_before", 0.0)),
            fit_brier_after=float(blob.get("fit_brier_after", 0.0)),
            is_identity=bool(blob.get("is_identity", not bps)),
        )

    @classmethod
    def load(cls, path: Path | str) -> "IsotonicCalibrator":
        """Load a calibrator JSON. Missing file -> identity."""
        p = Path(path)
        if not p.is_file():
            return cls.identity()
        try:
            blob = json.loads(p.read_text("utf-8"))
        except Exception:
            # A corrupt artifact must NEVER hide alerts from oncall.
            return cls.identity()
        return cls.from_dict(blob)

    # ── instance methods ─────────────────────────────────────────────

    def apply(self, p: float) -> float:
        """Map a raw probability to its calibrated value.

        Linear interpolation between the two enclosing breakpoints, with
        nearest-neighbour clamping outside the fitted range.
        """
        if not (0.0 <= p <= 1.0):
            raise ValueError(f"p must be in [0, 1], got {p!r}")
        if self.is_identity or not self.breakpoints:
            return p
        bps = self.breakpoints
        if p <= bps[0][0]:
            return max(0.0, min(1.0, bps[0][1]))
        if p >= bps[-1][0]:
            return max(0.0, min(1.0, bps[-1][1]))
        # Binary-search the interval.
        lo, hi = 0, len(bps) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if bps[mid][0] <= p:
                lo = mid
            else:
                hi = mid
        x0, y0 = bps[lo]
        x1, y1 = bps[hi]
        if math.isclose(x1, x0):
            out = y1
        else:
            t = (p - x0) / (x1 - x0)
            out = y0 + t * (y1 - y0)
        return max(0.0, min(1.0, out))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "breakpoints": [[round(x, 6), round(y, 6)] for x, y in self.breakpoints],
            "n_train": self.n_train,
            "fit_ece_before": round(self.fit_ece_before, 6),
            "fit_ece_after": round(self.fit_ece_after, 6),
            "fit_brier_before": round(self.fit_brier_before, 6),
            "fit_brier_after": round(self.fit_brier_after, 6),
            "is_identity": self.is_identity,
        }

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), "utf-8")
        tmp.replace(p)


# ──────────────────────────────────────────────────────────────────────────
# Bridge: feedback corpus -> (pred, outcome) pairs
# ──────────────────────────────────────────────────────────────────────────


def _verdict_to_outcome(verdict: str) -> int | None:
    """Map a verdict string to a binary outcome.

    Return None for verdicts that don't have a calibration signal (e.g.
    skipped, no_signal -- these are honest abstentions and shouldn't
    skew the calibrator).
    """
    if verdict in ("thumbs_up", "correct"):
        return 1
    if verdict in ("thumbs_down", "incorrect"):
        return 0
    return None


def gather_pairs_from_feedback(
    feedback_dir: Path | str,
) -> list[tuple[float, int]]:
    """Walk a feedback dir and extract every (agent_confidence, outcome) pair.

    Skips records that don't have `agent_confidence` set (e.g. records
    written before B3 landed) and records whose verdict doesn't map to
    a binary outcome (see `_verdict_to_outcome`).
    """
    d = Path(feedback_dir)
    if not d.is_dir():
        return []

    pairs: list[tuple[float, int]] = []
    for path in sorted(d.glob("*.json")):
        try:
            blob = json.loads(path.read_text("utf-8"))
        except Exception:
            continue
        for rec in blob.get("records", []):
            conf = rec.get("agent_confidence")
            if conf is None:
                continue
            outcome = _verdict_to_outcome(rec.get("verdict", ""))
            if outcome is None:
                continue
            try:
                p = float(conf)
            except (TypeError, ValueError):
                continue
            if 0.0 <= p <= 1.0:
                pairs.append((p, outcome))
    return pairs


# ──────────────────────────────────────────────────────────────────────────
# Markdown report
# ──────────────────────────────────────────────────────────────────────────


def render_markdown(
    report_before: CalibrationReport,
    *,
    calibrator: IsotonicCalibrator,
    report_after: CalibrationReport | None = None,
    feedback_dir: str | None = None,
    when: str = "",
) -> str:
    """Render a Markdown calibration report suitable for an auto-PR body."""
    lines: list[str] = []
    lines.append(f"# Calibration report{(' -- ' + when) if when else ''}")
    lines.append("")
    lines.append(
        "## Summary"
    )
    lines.append("")
    if calibrator.is_identity:
        lines.append(
            f"- **No calibrator fitted** "
            f"(n_pairs={report_before.n_pairs} below threshold or all-equal data)."
        )
        lines.append(
            f"- Corpus ECE: **{report_before.ece:.3f}**  ·  "
            f"Brier: **{report_before.brier:.3f}**"
        )
    else:
        delta_ece = report_before.ece - calibrator.fit_ece_after
        delta_brier = report_before.brier - calibrator.fit_brier_after
        lines.append(
            f"- Fitted on **n={calibrator.n_train}** pairs."
        )
        lines.append(
            f"- ECE: **{report_before.ece:.3f} -> "
            f"{calibrator.fit_ece_after:.3f}** "
            f"({_signed_pp(delta_ece)} on the training set)"
        )
        lines.append(
            f"- Brier: **{report_before.brier:.3f} -> "
            f"{calibrator.fit_brier_after:.3f}** "
            f"({_signed(delta_brier)})"
        )
    if feedback_dir:
        lines.append(f"- Source: `{feedback_dir}`")
    lines.append("")

    lines.append("## Reliability diagram (before)")
    lines.append("")
    lines.append("| bin           |   N | mean_pred | frac_correct | gap |")
    lines.append("|---------------|-----|-----------|--------------|-----|")
    for b in report_before.bins:
        if b.count == 0:
            lines.append(
                f"| [{b.low:.2f}, {b.high:.2f}) | {b.count:>3} |       --- |          --- |  -- |"
            )
            continue
        gap = b.mean_pred - b.frac_correct
        lines.append(
            f"| [{b.low:.2f}, {b.high:.2f}) | {b.count:>3} | "
            f"{b.mean_pred:>9.3f} | {b.frac_correct:>12.3f} | "
            f"{_signed_pp(gap)} |"
        )
    lines.append("")

    if report_after is not None and not calibrator.is_identity:
        lines.append("## Reliability diagram (after applying fitted calibrator)")
        lines.append("")
        lines.append("| bin           |   N | mean_pred | frac_correct | gap |")
        lines.append("|---------------|-----|-----------|--------------|-----|")
        for b in report_after.bins:
            if b.count == 0:
                lines.append(
                    f"| [{b.low:.2f}, {b.high:.2f}) | {b.count:>3} |       --- |          --- |  -- |"
                )
                continue
            gap = b.mean_pred - b.frac_correct
            lines.append(
                f"| [{b.low:.2f}, {b.high:.2f}) | {b.count:>3} | "
                f"{b.mean_pred:>9.3f} | {b.frac_correct:>12.3f} | "
                f"{_signed_pp(gap)} |"
            )
        lines.append("")

    if not calibrator.is_identity:
        lines.append("## Fitted breakpoints")
        lines.append("")
        lines.append("```")
        for x, y in calibrator.breakpoints:
            lines.append(f"raw={x:.3f}  ->  calibrated={y:.3f}")
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def _signed_pp(x: float) -> str:
    sign = "+" if x >= 0 else "-"
    return f"{sign}{abs(x) * 100:.1f}pp"


def _signed(x: float) -> str:
    sign = "+" if x >= 0 else "-"
    return f"{sign}{abs(x):.3f}"
