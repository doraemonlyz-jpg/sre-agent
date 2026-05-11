"""Trace Reader node — calls APM provider, optionally refines with LLM."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from sre_agent.logging import get_logger
from sre_agent.models import ModelRole, get_chat_model
from sre_agent.nodes._helpers import make_event
from sre_agent.personas import load as load_persona
from sre_agent.providers import get_provider
from sre_agent.schemas import EvidenceResult, GraphState, TracesEvidence

log = get_logger("trace_reader")


def trace_reader(state: GraphState) -> dict[str, Any]:
    alert = state["alert"]
    provider = get_provider()
    window_from = alert.started_at - timedelta(minutes=10)
    window_to = alert.started_at + timedelta(minutes=5)

    log.info("trace_reader.start", service=alert.service)

    try:
        if provider.name == "mock":
            ev = provider.fetch_traces(  # type: ignore[call-arg]
                service=alert.service,
                from_ts=window_from,
                to_ts=window_to,
                scenario_id=alert.scenario_id,
            )
        else:
            ev = provider.fetch_traces(
                service=alert.service,
                from_ts=window_from,
                to_ts=window_to,
            )
    except Exception as e:
        log.exception("trace_reader.fetch_failed", error=str(e))
        ev = TracesEvidence(
            result=EvidenceResult.ERROR,
            traces_inspected=0,
            error_rate="0/0",
            interpretation=f"APM API failed: {e}",
        )

    if ev.result == EvidenceResult.FOUND:
        ev = _refine_with_llm(ev, alert.service)

    return {
        "traces": ev,
        "events": [
            make_event(
                "trace-reader",
                "evidence",
                ev.interpretation,
                result=ev.result.value,
            )
        ],
    }


def _refine_with_llm(ev: TracesEvidence, service: str) -> TracesEvidence:
    try:
        persona = load_persona("trace-reader")
        llm = get_chat_model(ModelRole.ORCHESTRATOR)
        hot = ev.hot_span
        if hot:
            hot_line = (
                f"Hot span: {hot.service}.{hot.name} median={hot.median_ms}ms "
                f"(baseline {hot.baseline_ms}ms, {hot.ratio})"
            )
        else:
            hot_line = "No hot span detected."
        user = (
            f"Service: {service}\n"
            f"Traces inspected: {ev.traces_inspected}, error rate: {ev.error_rate}\n"
            f"{hot_line}\n"
            f"Downstream suspect: {ev.downstream_suspect or '(none)'}\n\n"
            "Write ONE sentence (<250 chars). Say where the latency is and what the shape suggests "
            "(lock contention / cold cache / connection pool / saturated downstream). No preamble."
        )
        out = llm.invoke([SystemMessage(content=persona), HumanMessage(content=user)])
        text = (out.content or "").strip().split("\n")[0][:380]
        if text:
            return ev.model_copy(update={"interpretation": text})
    except Exception as e:
        log.warning("trace_reader.llm_failed", error=str(e))
    return ev
