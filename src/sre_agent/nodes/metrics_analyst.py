"""Metrics Analyst node — symmetric to log_detective, but for metric snapshots."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from sre_agent.harness import bind_agent, record_persona_load
from sre_agent.logging import get_logger
from sre_agent.models import ModelRole, get_chat_model
from sre_agent.nodes._helpers import make_event
from sre_agent.personas import load_with_sha
from sre_agent.providers import get_provider
from sre_agent.schemas import EvidenceResult, GraphState, MetricsEvidence

log = get_logger("metrics_analyst")


def metrics_analyst(state: GraphState) -> dict[str, Any]:
    alert = state["alert"]
    provider = get_provider()
    window_from = alert.started_at - timedelta(minutes=10)
    window_to = alert.started_at + timedelta(minutes=5)

    log.info("metrics_analyst.start", service=alert.service)

    try:
        if provider.name == "mock":
            ev = provider.fetch_metrics(  # type: ignore[call-arg]
                service=alert.service,
                from_ts=window_from,
                to_ts=window_to,
                scenario_id=alert.scenario_id,
            )
        else:
            ev = provider.fetch_metrics(
                service=alert.service,
                from_ts=window_from,
                to_ts=window_to,
            )
    except Exception as e:
        log.exception("metrics_analyst.fetch_failed", error=str(e))
        ev = MetricsEvidence(
            result=EvidenceResult.ERROR,
            interpretation=f"Metrics API failed: {e}",
        )

    if ev.result == EvidenceResult.FOUND:
        ev = _refine_with_llm(ev, alert.service)

    return {
        "metrics": ev,
        "events": [
            make_event(
                "metrics-analyst",
                "evidence",
                f"{len([m for m in ev.metrics if m.is_spike])} spike(s) — {ev.interpretation}",
                result=ev.result.value,
            )
        ],
    }


def _refine_with_llm(ev: MetricsEvidence, service: str) -> MetricsEvidence:
    try:
        persona, _sha = load_with_sha("metrics-analyst")
        record_persona_load("metrics-analyst", _sha)
        llm = get_chat_model(ModelRole.ORCHESTRATOR)  # synthesis benefits from reasoning
        lines = [
            f"- {m.name}: baseline {m.baseline} → peak {m.peak} | verdict={m.verdict}"
            for m in ev.metrics
        ]
        user = (
            f"Service: {service}\n"
            f"Metrics snapshot:\n" + "\n".join(lines) + "\n"
            f"Correlation note: {ev.correlation or '(none)'}\n\n"
            "Write ONE sentence (<250 chars). Tell the on-call engineer what these "
            "metrics imply: traffic-driven? downstream-driven? capacity-driven? "
            "Or no signal. No preamble."
        )
        with bind_agent("metrics-analyst", prompt_sha=_sha):
            out = llm.invoke([SystemMessage(content=persona), HumanMessage(content=user)])
        text = (out.content or "").strip().split("\n")[0][:380]
        if text:
            return ev.model_copy(update={"interpretation": text})
    except Exception as e:
        log.warning("metrics_analyst.llm_failed", error=str(e))
    return ev
