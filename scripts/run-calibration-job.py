#!/usr/bin/env python3
"""
scripts/run-calibration-job.py -- L6.3 nightly calibrator-refit job.

Mirror of `run-winner-job.py` for the third leg of the L6 flywheel. The
GitHub Action invokes this binary; everything related to git / PR
creation stays in the workflow YAML.

What it does
------------
  1. Optionally seeds synthetic data (CI demo mode), or skips seeding
     (real prod reads from `SRE_FEEDBACK_DIR`).
  2. Fits an isotonic calibrator over the feedback corpus.
  3. Writes the calibrator JSON + Markdown report under
     `${REPORTS_DIR}/calibration-<UTC date>.{json,md}`.
  4. Decides whether to PROPOSE a calibrator update:
        propose = (n_pairs >= CAL_MIN_PAIRS) AND
                  (new_ece < current_ece - CAL_DELTA_THRESHOLD)
     (The default thresholds are conservative -- a 1pp ECE drop is
     statistical noise; we want at least 3pp before opening a PR.)
  5. Sets GitHub Action outputs:
        propose          true|false
        report_md        path to the Markdown report
        artifact_path    path to the new calibrator JSON (if proposed)
        date             UTC date stamp
  6. Exits 0 always; the workflow decides what to do with `propose`.

Env knobs
---------
  REPORTS_DIR              default ./reports
  SEED_N                   default 0 (set to seed before running)
  SEED_RNG                 default 42
  SEED_AB                  default 0.3
  CAL_OUT_PATH             default data/calibrator.json (the proposed update)
  CAL_CURRENT_PATH         default same as CAL_OUT_PATH (what's currently live)
  CAL_MIN_PAIRS            default 100
  CAL_DELTA_THRESHOLD      default 0.03 (3pp ECE drop required to propose)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _maybe_seed() -> None:
    n = int(_env("SEED_N", "0") or 0)
    if n <= 0:
        return
    print(f"[calibration-job] seeding {n} synthetic incidents...")
    from sre_agent.seed import seed
    seed(
        n=n,
        seed_value=int(_env("SEED_RNG", "42") or 42),
        ab_fraction=float(_env("SEED_AB", "0.3") or 0.3),
        reset_first=True,
    )


def _gha_output(key: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        print(f"::set-output {key}={value}")
        return
    with open(path, "a") as f:
        f.write(f"{key}={value}\n")


def main() -> int:
    from sre_agent.calibration import (
        IsotonicCalibrator,
        gather_pairs_from_feedback,
        render_markdown,
        summarize,
    )

    _maybe_seed()

    reports_dir = Path(_env("REPORTS_DIR", "./reports")).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    md_path = reports_dir / f"calibration-{today}.md"
    json_path = reports_dir / f"calibration-{today}.json"

    cal_out_path = Path(_env("CAL_OUT_PATH", "data/calibrator.json")).resolve()
    cal_current_path = Path(
        _env("CAL_CURRENT_PATH", str(cal_out_path)),
    ).resolve()
    min_pairs = int(_env("CAL_MIN_PAIRS", "100"))
    delta_threshold = float(_env("CAL_DELTA_THRESHOLD", "0.03"))

    feedback_dir = (
        _env("SRE_FEEDBACK_DIR", "")
        or str(Path.home() / ".sre-agent" / "feedback")
    )
    print(f"[calibration-job] reading feedback from {feedback_dir}")
    pairs = gather_pairs_from_feedback(feedback_dir)
    print(f"[calibration-job] found {len(pairs)} (confidence, outcome) pairs")

    before = summarize(pairs)
    new_cal = IsotonicCalibrator.fit(pairs, min_pairs=min_pairs)
    after = None
    if not new_cal.is_identity:
        after = summarize([(new_cal.apply(p), y) for p, y in pairs])

    # Compare to currently-live calibrator. If it doesn't exist on disk,
    # current_ece = before_ece (i.e. raw ECE without calibration applied).
    current = IsotonicCalibrator.load(cal_current_path)
    if current.is_identity:
        current_ece = before.ece
    else:
        # Apply current to the same pairs to measure live ECE.
        live_pairs = [(current.apply(p), y) for p, y in pairs]
        current_ece = summarize(live_pairs).ece

    new_ece = new_cal.fit_ece_after if not new_cal.is_identity else before.ece
    ece_drop = current_ece - new_ece

    propose = (
        not new_cal.is_identity
        and new_ece < current_ece - delta_threshold
    )
    reason: str
    if new_cal.is_identity:
        reason = f"too few pairs (n={len(pairs)} < min_pairs={min_pairs})"
    elif ece_drop < delta_threshold:
        reason = (
            f"new ECE {new_ece:.3f} not better than current {current_ece:.3f} "
            f"by required {delta_threshold:.3f} (got {ece_drop:+.3f})"
        )
    else:
        reason = (
            f"new ECE {new_ece:.3f} beats current {current_ece:.3f} "
            f"by {ece_drop:+.3f}"
        )
    print(f"[calibration-job] decision: propose={propose} -- {reason}")

    # Always write the artifacts so the run is auditable, but only stage
    # the artifact for PR adoption when we've decided to propose.
    md_body = render_markdown(
        before, calibrator=new_cal, report_after=after, feedback_dir=feedback_dir,
        when=today,
    )
    md_body += (
        f"\n## Decision\n\n"
        f"- **Propose update?** `{propose}`\n"
        f"- Current live ECE: `{current_ece:.3f}`\n"
        f"- New candidate ECE: `{new_ece:.3f}`\n"
        f"- ECE drop: `{ece_drop:+.3f}` "
        f"(threshold for propose: `{delta_threshold:.3f}`)\n"
        f"- Reason: {reason}\n"
    )
    md_path.write_text(md_body)
    json_path.write_text(json.dumps({
        "date": today,
        "n_pairs": before.n_pairs,
        "current_ece": current_ece,
        "new_ece": new_ece,
        "delta_threshold": delta_threshold,
        "propose": propose,
        "reason": reason,
        "calibrator": new_cal.to_dict(),
    }, indent=2))

    if propose:
        cal_out_path.parent.mkdir(parents=True, exist_ok=True)
        new_cal.save(cal_out_path)
        print(f"[calibration-job] wrote candidate calibrator -> {cal_out_path}")

    _gha_output("propose", "true" if propose else "false")
    _gha_output("report_md", str(md_path))
    _gha_output("report_json", str(json_path))
    _gha_output("artifact_path", str(cal_out_path) if propose else "")
    _gha_output("date", today)
    return 0


if __name__ == "__main__":
    sys.exit(main())
