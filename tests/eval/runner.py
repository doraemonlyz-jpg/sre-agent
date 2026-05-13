"""
Loader + runner for golden YAML cases.

Conceptually:

    yaml file → Case dataclass → run graph → IncidentReport dict → score_case

This file does the orchestration; `scoring.py` does the math. Kept separate
because the scorer is reusable from notebooks, CI, and the dashboard, but
the runner needs LangGraph imported.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from sre_agent.graph import build_graph
from sre_agent.schemas import AlertIn, GraphState, IncidentReport, Severity

from .scoring import CaseScore, ExpectedOutcome, score_case

CASES_DIR = Path(__file__).resolve().parent / "cases"


@dataclass
class GoldenCase:
    id: str
    description: str
    alert: AlertIn
    expected: ExpectedOutcome
    threshold: float
    requires_llm: bool
    tags: list[str]

    @classmethod
    def from_yaml(cls, path: Path) -> GoldenCase:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        a = data["alert"]
        alert = AlertIn(
            service=a["service"],
            severity=Severity(a["severity"]),
            description=a.get("description") or "",
            started_at=datetime.now(timezone.utc),
            tags=list(a.get("tags", [])),
            scenario_id=a.get("scenario_id"),
        )
        return cls(
            id=data["id"],
            description=data.get("description", ""),
            alert=alert,
            expected=ExpectedOutcome.from_dict(data.get("expected", {})),
            threshold=float(data.get("threshold", 0.8)),
            requires_llm=bool(data.get("requires_llm", False)),
            tags=list(data.get("tags", [])),
        )


def list_cases(cases_dir: Path = CASES_DIR) -> list[GoldenCase]:
    """Discover every .yaml under cases/, sorted by id."""
    if not cases_dir.is_dir():
        return []
    cases = []
    for p in sorted(cases_dir.glob("*.yaml")):
        try:
            cases.append(GoldenCase.from_yaml(p))
        except Exception as e:
            raise RuntimeError(f"failed to load case {p}: {e}") from e
    return cases


def run_case(case: GoldenCase) -> dict[str, Any]:
    """
    Run the LangGraph once for this case, return a flat dict matching the
    shape `score_case` expects. Each run gets a unique thread_id so the
    checkpointer doesn't replay a previous case's state.
    """
    graph = build_graph()
    thread_id = f"eval-{case.id}-{datetime.now(timezone.utc).timestamp():.0f}"
    config = {"configurable": {"thread_id": thread_id}}
    initial: GraphState = {"alert": case.alert, "events": []}

    # Drain the stream; we don't care about intermediate chunks here.
    for _ in graph.stream(initial, config=config):
        pass

    state = graph.get_state(config).values
    report: IncidentReport | None = state.get("report")

    # Mirror what `_evidence_to_legacy` etc. produce in the dashboard so
    # `score_case` can read the same shape from both entry points.
    out: dict[str, Any] = {
        "phase": getattr(report, "phase", "unknown") if report else "unknown",
        "findings": {},
        "hypothesis": None,
        "remediation": None,
        "report_json": (
            report.model_dump(mode="json", exclude_none=True) if report else None
        ),
    }

    # Evidence
    findings: dict[str, Any] = {}
    if (logs := state.get("logs")) is not None:
        findings["logs"] = logs.model_dump(mode="json", exclude_none=True)
    if (metrics := state.get("metrics")) is not None:
        findings["metrics"] = metrics.model_dump(mode="json", exclude_none=True)
    if (traces := state.get("traces")) is not None:
        findings["traces"] = traces.model_dump(mode="json", exclude_none=True)
    if (deploys := state.get("deploys")) is not None:
        findings["deploys"] = deploys.model_dump(mode="json", exclude_none=True)
    if (runbooks := state.get("runbooks")) is not None:
        findings["runbooks"] = runbooks.model_dump(mode="json", exclude_none=True)
    out["findings"] = findings

    # Hypothesis (flatten top → dict for scoring)
    hyps = state.get("hypotheses")
    if hyps and hyps.hypotheses:
        top = hyps.top
        out["hypothesis"] = {
            "title": top.title,
            "detail": top.detail,
            "confidence": top.confidence,
            "supporting_evidence": list(top.supporting_evidence),
            "contradicting_evidence": list(top.contradicting_evidence),
        }

    # Remediation
    rem = state.get("remediation")
    if rem:
        out["remediation"] = rem.model_dump(mode="json", exclude_none=True)

    return out


def score(case: GoldenCase, report: dict[str, Any]) -> CaseScore:
    """Wrapper so tests/test_eval.py reads cleanly."""
    return score_case(case.id, case.expected, report, threshold=case.threshold)
