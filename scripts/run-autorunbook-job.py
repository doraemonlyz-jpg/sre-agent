#!/usr/bin/env python3
"""
scripts/run-autorunbook-job.py — CI-friendly auto-runbook drafter.

Same shape as run-winner-job.py. Writes a Markdown draft of clustered
oncall corrections and sets `$GITHUB_OUTPUT` so the workflow can decide
whether to open a PR.

What it does
------------
  1. Optionally seeds synthetic data (CI demo mode).
  2. Runs `sre_agent.autorunbook.draft` against the feedback corpus.
  3. Writes `${REPORTS_DIR}/runbook-draft-<UTC date>.md`.
  4. Sets:
        draft=true|false       # any cluster above threshold?
        report_path=<md path>
        n_clusters=<int>

Env knobs
---------
  REPORTS_DIR     (default: ./reports)
  MIN_OCCURRENCES (default: 5)
  SEED_N          (default: 0)
  SEED_RNG        (default: 42)
  SEED_AB         (default: 0.3)
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _maybe_seed() -> None:
    n = int(_env("SEED_N", "0") or 0)
    if n <= 0:
        return
    print(f"[autorunbook-job] seeding {n} synthetic incidents…")
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
    from sre_agent.autorunbook import draft

    _maybe_seed()

    reports_dir = Path(_env("REPORTS_DIR", "./reports")).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    md_path = reports_dir / f"runbook-draft-{today}.md"

    report = draft(min_occurrences=int(_env("MIN_OCCURRENCES", "5")))

    md_path.write_text(report.to_markdown())

    n_clusters = len(report.clusters)
    print(
        f"[autorunbook-job] {n_clusters} cluster(s) above threshold "
        f"({report.skipped_below_threshold} suppressed)"
    )
    print(f"[autorunbook-job] report: {md_path}")

    _gha_output("draft", "true" if n_clusters > 0 else "false")
    _gha_output("report_md", str(md_path))
    _gha_output("n_clusters", str(n_clusters))
    _gha_output("date", today)

    return 0


if __name__ == "__main__":
    sys.exit(main())
