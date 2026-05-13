"""
Tests for the `sre-agent eval-drift` CLI command.

We don't shell out — we invoke the Typer app in-process and stub
the `run_case` / `score` functions so we don't need a live LLM.
The point of these tests is to verify:

  * The CLI honors --update-baseline (writes a baseline file).
  * On rerun, it computes drift = baseline - current.
  * It exits non-zero when drift exceeds --threshold.
  * --json output is parseable.
  * --require-llm flips the env var so requires_llm cases run.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from sre_agent.cli import app


@pytest.fixture
def stub_eval(monkeypatch, tmp_path):
    """Replace `run_case` + `score` so the CLI never touches the real graph."""

    class FakeResult:
        def __init__(self, score: float, threshold: float = 0.8):
            self.score = score
            self.threshold = threshold
            self.passed = score >= threshold
            self.checks = [("phase", True, "ok"), ("hypothesis", score > 0.5, "")]

    class FakeCase:
        def __init__(self, cid: str, requires_llm: bool, score: float, threshold: float):
            self.id = cid
            self.requires_llm = requires_llm
            self.threshold = threshold
            self._score = score

    cases = [
        FakeCase("happy", requires_llm=False, score=0.9, threshold=0.8),
        FakeCase("borderline", requires_llm=False, score=0.85, threshold=0.8),
        FakeCase("llm-only", requires_llm=True, score=0.92, threshold=0.85),
    ]

    def list_cases():
        return cases

    def run_case(case):
        # Returns a dict shaped like an incident report
        return {"phase": "diagnosed", "_id": case.id}

    def score(case, report):
        return FakeResult(case._score, case.threshold)

    import tests.eval.runner as runner_mod

    monkeypatch.setattr(runner_mod, "list_cases", list_cases)
    monkeypatch.setattr(runner_mod, "run_case", run_case)
    monkeypatch.setattr(runner_mod, "score", score)
    return cases


class TestEvalDriftCli:
    def test_update_baseline_writes_file(self, stub_eval, tmp_path):
        runner = CliRunner()
        baseline_path = tmp_path / "baseline.json"
        result = runner.invoke(
            app,
            [
                "eval-drift",
                "--baseline",
                str(baseline_path),
                "--update-baseline",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.stdout
        assert baseline_path.is_file()
        data = json.loads(baseline_path.read_text("utf-8"))
        # Offline run: llm-only case is skipped, others scored.
        assert data["scored"] == 2
        assert data["skipped"] == 1
        # mean of [0.9, 0.85] = 0.875
        assert abs(data["mean_score"] - 0.875) < 0.01

    def test_drift_within_threshold_succeeds(self, stub_eval, tmp_path):
        runner = CliRunner()
        baseline_path = tmp_path / "baseline.json"
        # First, set baseline at 0.875
        runner.invoke(
            app,
            [
                "eval-drift",
                "--baseline",
                str(baseline_path),
                "--update-baseline",
                "--json",
            ],
        )
        # Re-run — same fake stubs → same score, drift=0
        result = runner.invoke(
            app,
            ["eval-drift", "--baseline", str(baseline_path), "--threshold", "0.05", "--json"],
        )
        assert result.exit_code == 0, result.stdout

    def test_drift_over_threshold_exits_nonzero(self, monkeypatch, tmp_path):
        """If the current run is worse than baseline by more than --threshold,
        the CLI should exit 1 — this is the CI gate."""
        # Stash a baseline manually
        baseline = {"mean_score": 0.95}
        path = tmp_path / "baseline.json"
        path.write_text(json.dumps(baseline))

        # Stub cases to return 0.50 — a big drop
        class FakeResult:
            def __init__(self):
                self.score = 0.50
                self.threshold = 0.8
                self.passed = False
                self.checks = []

        class FakeCase:
            def __init__(self, cid):
                self.id = cid
                self.requires_llm = False
                self.threshold = 0.8

        import tests.eval.runner as runner_mod

        monkeypatch.setattr(runner_mod, "list_cases", lambda: [FakeCase("a")])
        monkeypatch.setattr(runner_mod, "run_case", lambda c: {"phase": "diagnosed"})
        monkeypatch.setattr(runner_mod, "score", lambda c, r: FakeResult())

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["eval-drift", "--baseline", str(path), "--threshold", "0.05", "--json"],
        )
        # drift = 0.95 - 0.5 = 0.45 > 0.05 → exit 1
        assert result.exit_code == 1

    def test_require_llm_flag_sets_env(self, stub_eval, monkeypatch, tmp_path):
        """`--require-llm` makes the requires_llm-tagged cases participate."""
        baseline_path = tmp_path / "baseline.json"
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "eval-drift",
                "--baseline",
                str(baseline_path),
                "--update-baseline",
                "--require-llm",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(baseline_path.read_text("utf-8"))
        # All 3 cases scored when --require-llm is on
        assert data["scored"] == 3
        assert data["skipped"] == 0
