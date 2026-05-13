"""
End-to-end evaluation harness — gated behind `-m eval`.

`pytest`              skips these (fast unit-test suite default).
`pytest -m eval -v`   runs the full graph once per case and asserts the
                      score crosses the case-defined threshold.

A case may declare `requires_llm: true` in its YAML. In offline mode
(the default `conftest._no_real_llm` fixture points at unreachable
Ollama) those cases are SKIPPED — their rule-based fallback can't reach
`diagnosed` because the fallback's confidence is 0.30 and `finalize`
needs >= 0.4. To run those cases, set `SRE_EVAL_REQUIRES_LLM=1` and
point `OLLAMA_BASE_URL` / `OPENAI_API_KEY` at a live model.

The runner / scoring / cases live in `tests/eval/`. This file is just the
pytest hook + a final aggregate report so a CI run prints a one-liner
like "8/10 cases passed, mean score 0.84".
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from tests.eval.runner import GoldenCase, list_cases, run_case, score

_CASES: list[GoldenCase] = list_cases()
_LIVE_LLM = bool(os.environ.get("SRE_EVAL_REQUIRES_LLM"))


def _id(case: GoldenCase) -> str:
    return case.id


@pytest.mark.eval
@pytest.mark.parametrize("case", _CASES, ids=[_id(c) for c in _CASES])
def test_golden_case(case: GoldenCase, request: pytest.FixtureRequest) -> None:
    if case.requires_llm and not _LIVE_LLM:
        pytest.skip(
            f"{case.id} requires a live LLM (rule-based fallback caps confidence "
            f"at 0.30, which finalize → no_signal). Set SRE_EVAL_REQUIRES_LLM=1 "
            f"and OLLAMA_BASE_URL / OPENAI_API_KEY to run."
        )
    """
    Run the LangGraph for one golden case and assert the score crosses
    the case-defined threshold. On failure, the full per-check breakdown
    is printed so a developer can see exactly which dimension regressed.
    """
    report = run_case(case)
    result = score(case, report)

    # Stash on request.node so test_eval_summary can aggregate at the end.
    node_results: dict[str, Any] = request.config.cache.get("eval/results", {}) or {}
    node_results[case.id] = {
        "score": result.score,
        "passed": result.passed,
        "threshold": result.threshold,
        "checks": [(n, ok, d) for n, ok, d in result.checks],
        "phase": report.get("phase"),
    }
    request.config.cache.set("eval/results", node_results)

    # Print the per-check breakdown so `-v` shows it immediately.
    print("\n" + result.report())

    assert result.passed, (
        f"\nCase {case.id} scored {result.score:.2f} < threshold {result.threshold:.2f}\n"
        + result.report()
    )


@pytest.mark.eval
def test_eval_summary(request: pytest.FixtureRequest) -> None:
    """
    Aggregate report. Always passes; its purpose is to print the summary
    last so CI logs end with a clean leaderboard.
    """
    results: dict[str, Any] = request.config.cache.get("eval/results", {}) or {}
    if not results:
        pytest.skip("no per-case results recorded — run the parametrized eval first")

    passed = sum(1 for v in results.values() if v["passed"])
    total = len(results)
    mean = sum(v["score"] for v in results.values()) / total

    lines = [
        "",
        "=" * 60,
        "EVAL SUMMARY",
        "=" * 60,
        f"Passed:     {passed}/{total}",
        f"Mean score: {mean:.2f}",
        "",
    ]
    for cid, v in sorted(results.items()):
        status = "PASS" if v["passed"] else "FAIL"
        lines.append(
            f"  {status:5s}  {cid:40s}  score={v['score']:.2f}  "
            f"thr={v['threshold']:.2f}  phase={v.get('phase')}"
        )
    print("\n".join(lines))
