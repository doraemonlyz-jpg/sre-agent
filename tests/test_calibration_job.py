"""
Tests for scripts/run-calibration-job.py -- B2.

We don't import the script directly (it's a `__main__`-style binary).
Instead we invoke it as a subprocess so we cover the actual entry
point + GHA-output side effects.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def cal_env(tmp_path, monkeypatch):
    """Set up an isolated feedback + reports + data dir tree."""
    feedback = tmp_path / "feedback"
    reports = tmp_path / "reports"
    data = tmp_path / "data"
    gha_out = tmp_path / "gha-output.txt"
    for p in (feedback, reports, data):
        p.mkdir()
    gha_out.touch()

    env = {
        "SRE_FEEDBACK_DIR":    str(feedback),
        "REPORTS_DIR":         str(reports),
        "CAL_OUT_PATH":        str(data / "calibrator.json"),
        "CAL_CURRENT_PATH":    str(data / "calibrator.json"),
        "CAL_MIN_PAIRS":       "50",
        # We seed deterministically; the achievable ECE drop on the
        # synthetic distribution depends on which scenarios are loaded
        # (the seeder consults MockProvider's scenario list, which now
        # has 10 entries vs. the original 3). Use a 1pp threshold here
        # so the test asserts the auto-PR pipeline FIRES, not that the
        # synthetic data happens to support a 3pp improvement -- the
        # latter is brittle and not what we're testing.
        "CAL_DELTA_THRESHOLD": "0.01",
        "GITHUB_OUTPUT":       str(gha_out),
        # PYTHONPATH wiring so the subprocess sees the same checkout
        # we're testing.
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
    }
    return {
        "env": env,
        "feedback": feedback,
        "reports": reports,
        "data": data,
        "gha_out": gha_out,
    }


def _run_job(env_overrides: dict, seed_n: int) -> subprocess.CompletedProcess:
    import os
    script = Path(__file__).resolve().parents[1] / "scripts" / "run-calibration-job.py"
    e = dict(os.environ)
    e.update(env_overrides)
    e["SEED_N"] = str(seed_n)
    e.setdefault("SEED_RNG", "42")
    e.setdefault("SEED_AB", "0.3")
    return subprocess.run(
        [sys.executable, str(script)],
        env=e,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _read_gha(gha_out: Path) -> dict[str, str]:
    out = {}
    for line in gha_out.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


class TestProposePath:
    def test_seeds_and_proposes_update_with_enough_data(self, cal_env):
        result = _run_job(cal_env["env"], seed_n=3000)
        assert result.returncode == 0, f"job failed: {result.stderr}"

        gha = _read_gha(cal_env["gha_out"])
        assert gha["propose"] == "true", f"expected proposal, got: {gha}\n{result.stdout}"

        # Calibrator was written to disk
        assert (cal_env["data"] / "calibrator.json").exists()
        loaded = json.loads((cal_env["data"] / "calibrator.json").read_text())
        # Calibrator artifact has the expected top-level keys
        assert "breakpoints" in loaded
        assert "n_train" in loaded

        # Reports were emitted
        report_md_path = Path(gha["report_md"])
        report_json_path = Path(gha["report_json"])
        assert report_md_path.exists()
        assert report_json_path.exists()

        # Markdown report has a decision section
        md = report_md_path.read_text()
        assert "## Decision" in md
        assert "**Propose update?** `True`" in md
        assert "ECE drop:" in md

        # JSON report has the right keys
        rj = json.loads(report_json_path.read_text())
        assert rj["propose"] is True
        assert rj["new_ece"] < rj["current_ece"]


class TestNoProposePath:
    def test_too_few_pairs_does_not_propose(self, cal_env):
        # Force a very high min_pairs so even 3000 seed incidents
        # produce too-few qualifying pairs.
        env = dict(cal_env["env"])
        env["CAL_MIN_PAIRS"] = "999999"

        result = _run_job(env, seed_n=3000)
        assert result.returncode == 0, f"job failed: {result.stderr}"

        gha = _read_gha(cal_env["gha_out"])
        assert gha["propose"] == "false"
        assert gha["artifact_path"] == ""

    def test_high_threshold_does_not_propose(self, cal_env):
        # Force the propose threshold higher than any realistic drop.
        env = dict(cal_env["env"])
        env["CAL_DELTA_THRESHOLD"] = "0.50"

        result = _run_job(env, seed_n=3000)
        assert result.returncode == 0, f"job failed: {result.stderr}"

        gha = _read_gha(cal_env["gha_out"])
        assert gha["propose"] == "false"


class TestAlwaysWritesReports:
    def test_artifact_path_empty_when_not_proposing(self, cal_env):
        env = dict(cal_env["env"])
        env["CAL_DELTA_THRESHOLD"] = "0.99"  # impossible to clear

        result = _run_job(env, seed_n=2000)
        assert result.returncode == 0

        gha = _read_gha(cal_env["gha_out"])
        assert gha["propose"] == "false"
        assert gha["artifact_path"] == ""

        # Reports are still on disk -- important for auditing the
        # decision even when we don't open a PR.
        assert Path(gha["report_md"]).exists()
        assert Path(gha["report_json"]).exists()
