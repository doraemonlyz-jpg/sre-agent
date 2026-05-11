"""
Hypothesis Generator node — the brain.

Gathers all 4 evidence sources from state, asks the LLM (with structured output)
for 1–5 ranked root-cause hypotheses with citations.

If the LLM fails or returns nonsense, we fall back to a rule-based hypothesis
so the pipeline still produces a result (low confidence). This is critical for
production: an on-call engineer should ALWAYS see *something*, even if it's
"we couldn't reach the LLM".
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from sre_agent.logging import get_logger
from sre_agent.models import ModelRole, get_chat_model
from sre_agent.nodes._helpers import make_event
from sre_agent.personas import load as load_persona
from sre_agent.schemas import (
    EvidenceResult,
    GraphState,
    Hypothesis,
    HypothesisList,
)

log = get_logger("hypothesis_gen")


def hypothesis_generator(state: GraphState) -> dict[str, Any]:
    alert = state["alert"]
    logs = state.get("logs")
    metrics = state.get("metrics")
    traces = state.get("traces")
    deploys = state.get("deploys")
    runbooks = state.get("runbooks")

    log.info("hypothesis_gen.start", service=alert.service)

    # Quick check: did anyone find anything? Runbooks count as a signal — if
    # we have a high-confidence match for a known failure pattern, the LLM
    # can still produce a useful hypothesis even when live telemetry is thin.
    any_found = any(
        ev is not None and ev.result == EvidenceResult.FOUND
        for ev in (logs, metrics, traces, deploys, runbooks)
    )
    if not any_found:
        return _no_signal_result()

    try:
        persona = load_persona("hypothesis-gen")
        llm = get_chat_model(ModelRole.ORCHESTRATOR).with_structured_output(
            HypothesisList, include_raw=False
        )
        user = _build_synthesis_prompt(alert, logs, metrics, traces, deploys, runbooks)
        out: HypothesisList = llm.invoke(
            [SystemMessage(content=persona), HumanMessage(content=user)]
        )  # type: ignore[assignment]
        top = out.top
        return {
            "hypotheses": out,
            "events": [
                make_event(
                    "hypothesis-generator",
                    "evidence",
                    f"Top hypothesis ({int(top.confidence*100)}%): {top.title}",
                    n_hypotheses=len(out.hypotheses),
                )
            ],
        }
    except Exception as e:
        log.exception("hypothesis_gen.llm_failed", error=str(e))
        return _fallback_from_evidence(state, str(e))


def _build_synthesis_prompt(alert, logs, metrics, traces, deploys, runbooks=None) -> str:
    sections = [f"# Alert\n{alert.severity.value} on {alert.service}: {alert.description}"]
    if logs:
        sections.append(
            f"# Logs ({logs.result.value})\n"
            f"hits={logs.hits}, peak_at={logs.peak_at}\n"
            f"interpretation: {logs.interpretation}\n"
            f"top: {logs.top_messages[:2]}"
        )
    if metrics:
        spike_summary = ", ".join(
            f"{m.name}={m.verdict}" for m in metrics.metrics
        ) if metrics.metrics else "(no data)"
        sections.append(
            f"# Metrics ({metrics.result.value})\n"
            f"{spike_summary}\n"
            f"correlation: {metrics.correlation or '(none)'}\n"
            f"interpretation: {metrics.interpretation}"
        )
    if traces:
        hot = traces.hot_span
        sections.append(
            f"# Traces ({traces.result.value})\n"
            f"error_rate={traces.error_rate}, traces_inspected={traces.traces_inspected}\n"
            f"hot_span: {hot.service+'.'+hot.name if hot else '(none)'} "
            f"@ {hot.median_ms if hot else '?'}ms ({hot.ratio if hot else '?'})\n"
            f"downstream: {traces.downstream_suspect or '(none)'}\n"
            f"interpretation: {traces.interpretation}"
        )
    if deploys:
        d_summary = "; ".join(
            f"{d.service}@{d.sha[:7]} ({d.minutes_before:.0f}min before, suspect={d.suspect})"
            for d in deploys.deploys
        ) or "(none)"
        sections.append(
            f"# Deploys ({deploys.result.value})\n"
            f"{d_summary}\n"
            f"interpretation: {deploys.interpretation}"
        )
    if runbooks and runbooks.result == EvidenceResult.FOUND and runbooks.hits:
        # The runbook chunks are the team's prior knowledge — known failure
        # modes, past-incident postmortems, oncall playbooks. We surface
        # them VERBATIM so the LLM can cite them concretely rather than
        # paraphrasing into a hallucination.
        rb_lines: list[str] = []
        for i, h in enumerate(runbooks.hits, start=1):
            rb_lines.append(
                f"## Runbook #{i}: '{h.title}' (from `{h.path}`, score={h.score:.2f})\n"
                f"{h.snippet}"
            )
        sections.append(
            "# Team runbooks (prior knowledge — cite by file path when used)\n"
            + "\n\n".join(rb_lines)
        )
    sections.append(
        "# Your task\n"
        "Produce 1–3 ranked hypotheses with confidence 0–1. Cite supporting "
        "AND contradicting evidence sources by name "
        "(logs|metrics|traces|deploys|runbooks). "
        "If a team runbook documents this exact pattern, MENTION THE RUNBOOK "
        "FILE PATH in the hypothesis detail (e.g. 'see runbooks/chaos-app.md'). "
        "For the top hypothesis, briefly explain why the next-best alternative is less likely."
    )
    return "\n\n".join(sections)


def _no_signal_result() -> dict[str, Any]:
    """All 4 workers returned NO_SIGNAL — we say so explicitly."""
    return {
        "hypotheses": HypothesisList(
            hypotheses=[
                Hypothesis(
                    title="NO SIGNAL — possible false-positive alert",
                    detail=(
                        "All four investigators (logs, metrics, traces, deploys) returned NO_SIGNAL. "
                        "Either the alert is a false positive, the time window is wrong, or the issue "
                        "is in a system we don't monitor."
                    ),
                    confidence=0.50,
                    supporting_evidence=[],
                    contradicting_evidence=["logs", "metrics", "traces", "deploys"],
                    why_not_alternative="No alternative — nothing was found.",
                )
            ],
            notes="No evidence found across any investigator.",
        ),
        "events": [
            make_event(
                "hypothesis-generator",
                "evidence",
                "NO SIGNAL — possible false-positive alert.",
            )
        ],
    }


def _fallback_from_evidence(state: GraphState, err: str) -> dict[str, Any]:
    """LLM down — synthesize a minimal hypothesis from rule-based evidence."""
    bits = []
    if (deploys := state.get("deploys")) and deploys.result == EvidenceResult.FOUND and deploys.deploys:
        top = deploys.deploys[0]
        bits.append(f"a recent deploy ({top.service} {top.sha[:7]})")
    if (metrics := state.get("metrics")) and metrics.result == EvidenceResult.FOUND and metrics.correlation:
        bits.append(metrics.correlation)
    if (traces := state.get("traces")) and traces.result == EvidenceResult.FOUND and traces.hot_span:
        bits.append(f"a hot span in {traces.hot_span.name}")
    # If the runbook consultant matched a known pattern, surface it in the
    # fallback too — even without an LLM, telling oncall "this matches the
    # documented connection-pool runbook" is high-value.
    if (rb := state.get("runbooks")) and rb.result == EvidenceResult.FOUND and rb.hits:
        bits.append(f"runbook match: '{rb.hits[0].title}' ({rb.hits[0].path})")
    detail = (
        "LLM unavailable — rule-based fallback. Evidence suggests: "
        + (", ".join(bits) if bits else "no clear signal")
        + f". LLM error: {err[:120]}"
    )
    return {
        "hypotheses": HypothesisList(
            hypotheses=[
                Hypothesis(
                    title="Rule-based fallback (LLM unavailable)",
                    detail=detail,
                    confidence=0.30,
                    supporting_evidence=[
                        k for k in ("logs", "metrics", "traces", "deploys", "runbooks")
                        if (e := state.get(k)) and e.result == EvidenceResult.FOUND  # type: ignore[union-attr]
                    ],
                )
            ],
            notes=f"LLM error: {err[:160]}",
        ),
        "events": [
            make_event(
                "hypothesis-generator",
                "error",
                f"LLM failed; used rule-based fallback. ({err[:80]})",
            )
        ],
    }
