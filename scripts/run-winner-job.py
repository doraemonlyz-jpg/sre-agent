#!/usr/bin/env python3
"""
scripts/run-winner-job.py — CI-friendly winner-promotion job.

This is the binary the GitHub Action invokes. Keeping it in Python (vs.
inline YAML) means:

  1. The same job is reproducible from a laptop with one command,
     which matters when you're debugging "why did CI open this PR".
  2. We can unit test it (it's just `subprocess`+`pathlib`, no
     git/PR logic — that part stays in the workflow).
  3. The contract with the Action is small: stdout = human summary,
     exit code = "did we want to open a PR?", artifact paths
     written to `$GITHUB_OUTPUT` so the next step can read them.

What it does
------------
  1. Optionally seeds synthetic data (CI demo mode), or skips the seed
     (real prod mode reads `SRE_FEEDBACK_DIR`).
  2. Runs `sre_agent.winner.analyze` against the feedback corpus with
     a configured baseline map.
  3. Writes the Markdown report + JSON report under
     `${REPORTS_DIR}/winner-<UTC date>.{md,json}`.
  4. Sets two `$GITHUB_OUTPUT` values:
        promote=true|false      # any agent recommended for promotion?
        report_path=<md path>
  5. Exits 0 always (the workflow makes its own decisions).

Env knobs
---------
  REPORTS_DIR         (default: ./reports)
  BASELINES           (default: 'hypothesis-gen=0c8f14d5')
  SEED_N              (default: 0 — set non-zero to seed before running)
  SEED_RNG            (default: 42)
  SEED_AB             (default: 0.3)
  WINNER_ALPHA        (default: 0.05)
  WINNER_MIN_N        (default: 50)
  WINNER_MIN_DELTA_PP (default: 3.0)
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
    print(f"[winner-job] seeding {n} synthetic incidents…")
    from sre_agent.seed import seed
    seed(
        n=n,
        seed_value=int(_env("SEED_RNG", "42") or 42),
        ab_fraction=float(_env("SEED_AB", "0.3") or 0.3),
        reset_first=True,
    )


def _parse_baselines(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece or "=" not in piece:
            continue
        agent, sha = piece.split("=", 1)
        out[agent.strip()] = sha.strip()
    return out


def _gha_output(key: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        # Local dev: print so the user sees what would be exported.
        print(f"::set-output {key}={value}")
        return
    with open(path, "a") as f:
        f.write(f"{key}={value}\n")


def main() -> int:
    from sre_agent.winner import analyze, to_json

    _maybe_seed()

    reports_dir = Path(_env("REPORTS_DIR", "./reports")).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    md_path = reports_dir / f"winner-{today}.md"
    json_path = reports_dir / f"winner-{today}.json"

    baselines = _parse_baselines(
        _env("BASELINES", "hypothesis-gen=0c8f14d5")
    )

    report = analyze(
        baselines=baselines,
        alpha=float(_env("WINNER_ALPHA", "0.05")),
        min_per_group=int(_env("WINNER_MIN_N", "50")),
        min_delta_pp=float(_env("WINNER_MIN_DELTA_PP", "3.0")),
    )

    md_path.write_text(report.to_markdown())
    json_path.write_text(to_json(report))

    n_promote = sum(1 for d in report.decisions if d.verdict == "promote")
    n_hold = sum(1 for d in report.decisions if d.verdict == "hold")

    print(
        f"[winner-job] decisions: {n_promote} promote, {n_hold} hold, "
        f"{len(report.decisions) - n_promote - n_hold} no-data"
    )
    print(f"[winner-job] reports: {md_path}, {json_path}")

    # CI integration: set outputs for the workflow to consume.
    _gha_output("promote", "true" if n_promote > 0 else "false")
    _gha_output("report_md", str(md_path))
    _gha_output("report_json", str(json_path))
    _gha_output("date", today)

    # Also dump a compact line on stdout so the workflow log is useful
    # even without artifact download.
    promoted = [
        {"agent": d.agent, "from": d.runner_up_sha, "to": d.winner_sha,
         "delta_pp": round(d.delta_pp, 1), "p": round(d.p_value, 4)}
        for d in report.decisions if d.verdict == "promote"
    ]
    print("[winner-job] promoted=" + json.dumps(promoted))

    return 0


if __name__ == "__main__":
    sys.exit(main())
