"""
Remediation Suggester node.

CRITICAL: this node NEVER executes anything. Its output is a list of suggested
commands for a human to copy-paste. The persona enforces this and the schema
constrains the action shape (must include `reversal` for every action).
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from sre_agent.harness import bind_agent, record_persona_load
from sre_agent.logging import get_logger
from sre_agent.models import ModelRole, get_chat_model
from sre_agent.nodes._helpers import make_event
from sre_agent.personas import load_with_sha
from sre_agent.retry import with_retries
from sre_agent.schemas import (
    EvidenceResult,
    GraphState,
    HypothesisList,
    RemediationAction,
    RemediationPlan,
    RemediationRisk,
    RunbookEvidence,
)

log = get_logger("remediation_sug")


def remediation_suggester(state: GraphState) -> dict[str, Any]:
    hyps = state.get("hypotheses")
    if not hyps or not hyps.hypotheses:
        return _empty_plan()

    log.info("remediation_sug.start", top=hyps.top.title)

    runbooks = state.get("runbooks")

    try:
        persona, _sha = load_with_sha("remediation-sug")
        record_persona_load("remediation-sug", _sha)
        llm = get_chat_model(ModelRole.ORCHESTRATOR).with_structured_output(
            RemediationPlan, include_raw=False
        )
        user = _build_prompt(hyps, runbooks)
        with bind_agent("remediation-sug", prompt_sha=_sha):
            plan: RemediationPlan = with_retries(
                lambda: llm.invoke(
                    [SystemMessage(content=persona), HumanMessage(content=user)]
                ),
                agent="remediation-sug",
            )  # type: ignore[assignment]
        return {
            "remediation": plan,
            "events": [
                make_event(
                    "remediation-suggester",
                    "evidence",
                    f"{len(plan.actions)} suggested action(s); {len(plan.do_not_do)} anti-pattern(s).",
                    actions=len(plan.actions),
                )
            ],
        }
    except Exception as e:
        log.exception("remediation_sug.llm_failed", error=str(e))
        return _fallback_plan(hyps, str(e))


def _build_prompt(hyps: HypothesisList, runbooks: RunbookEvidence | None = None) -> str:
    top = hyps.top
    others = [h for h in hyps.hypotheses if h is not top]
    lines = [
        "# Top hypothesis",
        f"Title: {top.title}",
        f"Confidence: {top.confidence:.2f}",
        f"Detail: {top.detail}",
        "",
    ]
    if others:
        lines.append("# Other hypotheses (also possible)")
        for h in others:
            lines.append(f"- {h.title} (conf={h.confidence:.2f})")
        lines.append("")
    if runbooks and runbooks.result == EvidenceResult.FOUND and runbooks.hits:
        # If the team has documented this pattern, the runbook chunks
        # often contain literal mitigation commands. Surface them so the
        # LLM lifts them verbatim rather than inventing kubectl invocations.
        lines.append("# Team runbooks (extract concrete commands from these if relevant)")
        for h in runbooks.hits:
            lines.append(f"## From `{h.path}` — '{h.title}' (score={h.score:.2f})")
            lines.append(h.snippet)
            lines.append("")
    lines.append(
        "# Your task\n"
        "Suggest 1-3 remediation actions a human on-call could try, ordered safest-first. "
        "Each MUST include a `reversal` command. NEVER suggest auto-execution. "
        "Add 1-3 anti-patterns the on-call should AVOID.\n"
        "If a team runbook above contains a literal mitigation command, "
        "USE IT VERBATIM and cite the runbook path in the `why` field "
        "(e.g. 'see runbooks/chaos-app.md').\n"
        "Risk levels: LOW (read-only/restart), MEDIUM (config change), HIGH (data write/rollback)."
    )
    return "\n".join(lines)


def _empty_plan() -> dict[str, Any]:
    return {
        "remediation": RemediationPlan(
            actions=[],
            do_not_do=[
                "Don't blindly restart everything — that hides the real root cause."
            ],
        ),
        "events": [
            make_event(
                "remediation-suggester",
                "evidence",
                "No hypotheses to remediate against.",
            )
        ],
    }


def _fallback_plan(hyps: HypothesisList, err: str) -> dict[str, Any]:
    top = hyps.top
    return {
        "remediation": RemediationPlan(
            actions=[
                RemediationAction(
                    title="Page a human SRE (LLM unavailable)",
                    command="echo 'LLM unavailable — escalate to on-call SRE'",
                    why=f"Top hypothesis was: {top.title}",
                    expected_effect="Human pickup of the incident.",
                    reversal="N/A",
                    risk=RemediationRisk.NONE,
                )
            ],
            do_not_do=[
                "Don't take any automatic action — the LLM diagnostic failed: "
                + err[:120],
            ],
        ),
        "events": [
            make_event(
                "remediation-suggester",
                "error",
                f"LLM failed; recommending human escalation. ({err[:80]})",
            )
        ],
    }
