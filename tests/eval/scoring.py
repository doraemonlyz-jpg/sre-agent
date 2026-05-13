"""
Pure scoring functions for the eval harness.

NO I/O in this file — given a `Report`-ish dict and an `ExpectedOutcome`,
return a `CaseScore`. Tests in `tests/test_eval.py` do the orchestration
(load YAML, build graph, run it, call score_case).

The point is that you can `python -c "from tests.eval.scoring import
score_case; ..."` to debug a single case without spinning up pytest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ──────────────────────────────────────────────────────────────────────────
# Schemas — kept as plain dataclasses so we have no runtime dep on Pydantic
# in the scoring path (it's already a dep, but easier to reuse externally).
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class ExpectedOutcome:
    phase: list[str] | None = None
    must_not_phase: list[str] | None = None
    must_cite_evidence: list[str] | None = None
    hypothesis_keywords_any: list[str] | None = None
    runbook_path_contains: str | None = None
    confidence_range: tuple[float, float] | None = None
    remediation_action_titles_any: list[str] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExpectedOutcome:
        cr = d.get("confidence_range")
        cr_t = (float(cr[0]), float(cr[1])) if isinstance(cr, list) and len(cr) == 2 else None
        return cls(
            phase=d.get("phase"),
            must_not_phase=d.get("must_not_phase"),
            must_cite_evidence=d.get("must_cite_evidence"),
            hypothesis_keywords_any=d.get("hypothesis_keywords_any"),
            runbook_path_contains=d.get("runbook_path_contains"),
            confidence_range=cr_t,
            remediation_action_titles_any=d.get("remediation_action_titles_any"),
        )


@dataclass
class CaseScore:
    case_id: str
    score: float
    passed: bool
    threshold: float
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def report(self) -> str:
        lines = [
            f"== {self.case_id} ==  score={self.score:.2f}  threshold={self.threshold:.2f}  "
            f"{'PASS' if self.passed else 'FAIL'}"
        ]
        for name, ok, detail in self.checks:
            mark = "  ok  " if ok else "  !!  "
            lines.append(f"{mark}{name}: {detail}")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# The scorer — works against the dashboard's incident-dict shape *or* a raw
# IncidentReport. We accept both because the dashboard is the natural entry
# for E2E tests, but the report is what you'd get out of the CLI.
# ──────────────────────────────────────────────────────────────────────────


def _get_hypothesis(report: dict[str, Any]) -> dict[str, Any] | None:
    """Return the top hypothesis as a dict, regardless of input shape."""
    h = report.get("hypothesis")
    if isinstance(h, dict):
        return h
    # Maybe it's a HypothesisList shape:
    if isinstance(h, dict) and "top" in h:
        return h["top"]
    # Maybe we were given report_json
    rj = report.get("report_json")
    if isinstance(rj, dict):
        return _get_hypothesis(rj)
    return None


def _get_supporting_evidence(report: dict[str, Any]) -> list[str]:
    h = _get_hypothesis(report) or {}
    supp = h.get("supporting_evidence") or h.get("supporting") or []
    return [str(x).lower() for x in supp]


def _get_runbook_paths(report: dict[str, Any]) -> list[str]:
    findings = report.get("findings") or {}
    rb = findings.get("runbooks") or {}
    hits = rb.get("hits") or []
    paths: list[str] = []
    for h in hits:
        if isinstance(h, dict) and h.get("path"):
            paths.append(str(h["path"]))
    # Also check report_json if findings is empty
    if not paths:
        rj = (report.get("report_json") or {}).get("evidence") or {}
        rj_rb = rj.get("runbooks") or {}
        for h in rj_rb.get("hits") or []:
            if isinstance(h, dict) and h.get("path"):
                paths.append(str(h["path"]))
    return paths


def _get_remediation_titles(report: dict[str, Any]) -> list[str]:
    rem = report.get("remediation") or {}
    actions = rem.get("actions") or []
    out = []
    for a in actions:
        if isinstance(a, dict):
            t = a.get("title") or a.get("command") or ""
            if t:
                out.append(str(t).lower())
    return out


def score_case(
    case_id: str,
    expected: ExpectedOutcome,
    report: dict[str, Any],
    *,
    threshold: float = 0.8,
) -> CaseScore:
    """Run every defined check against `report`, return a `CaseScore`."""
    checks: list[tuple[str, bool, str]] = []

    phase = (report.get("phase") or "").lower()

    if expected.phase:
        allowed = {p.lower() for p in expected.phase}
        ok = phase in allowed
        checks.append(("phase", ok, f"got={phase!r} expected_any_of={sorted(allowed)}"))

    if expected.must_not_phase:
        forbidden = {p.lower() for p in expected.must_not_phase}
        ok = phase not in forbidden
        checks.append(
            ("must_not_phase", ok, f"got={phase!r} forbidden={sorted(forbidden)}")
        )

    if expected.must_cite_evidence:
        supp = set(_get_supporting_evidence(report))
        expected_set = {x.lower() for x in expected.must_cite_evidence}
        missing = expected_set - supp
        ok = not missing
        checks.append(
            ("must_cite_evidence", ok, f"missing={sorted(missing)} cited={sorted(supp)}")
        )

    if expected.hypothesis_keywords_any:
        h = _get_hypothesis(report) or {}
        text = (str(h.get("title", "")) + " " + str(h.get("detail", ""))).lower()
        # str() each keyword because YAML happily parses bare `502` as int.
        kws = [str(kw) for kw in expected.hypothesis_keywords_any]
        hits = [kw for kw in kws if kw.lower() in text]
        ok = bool(hits)
        checks.append(
            (
                "hypothesis_keywords_any",
                ok,
                f"matched={hits} candidates={kws}",
            )
        )

    if expected.runbook_path_contains:
        paths = _get_runbook_paths(report)
        ok = any(expected.runbook_path_contains.lower() in p.lower() for p in paths)
        checks.append(
            (
                "runbook_path_contains",
                ok,
                f"needle={expected.runbook_path_contains!r} paths={paths[:3]}",
            )
        )

    if expected.confidence_range:
        h = _get_hypothesis(report) or {}
        conf = h.get("confidence")
        lo, hi = expected.confidence_range
        if isinstance(conf, (int, float)):
            ok = lo <= conf <= hi
            checks.append(
                ("confidence_range", ok, f"got={conf:.2f} range=[{lo:.2f},{hi:.2f}]")
            )
        else:
            checks.append(
                ("confidence_range", False, f"no numeric confidence in hypothesis: {conf!r}")
            )

    if expected.remediation_action_titles_any:
        titles = _get_remediation_titles(report)
        kws = [str(kw) for kw in expected.remediation_action_titles_any]
        hits = [kw for kw in kws if any(kw.lower() in t for t in titles)]
        ok = bool(hits)
        checks.append(
            (
                "remediation_action_titles_any",
                ok,
                f"matched={hits} titles={titles[:3]}",
            )
        )

    if not checks:
        # Nothing was asked of this case — that's a usage error. Score 0
        # to make it loud.
        return CaseScore(case_id=case_id, score=0.0, passed=False, threshold=threshold)

    score = sum(1 for _, ok, _ in checks if ok) / len(checks)
    return CaseScore(
        case_id=case_id,
        score=score,
        passed=score >= threshold,
        threshold=threshold,
        checks=checks,
    )
