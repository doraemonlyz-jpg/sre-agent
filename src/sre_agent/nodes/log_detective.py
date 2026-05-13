"""
Log Detective node.

Flow:
1. Call provider.fetch_logs() to get a structured LogsEvidence.
2. If we found anomalies, ask the LLM to write a one-sentence interpretation
   based on the persona prompt + the raw evidence.
3. Return the (possibly LLM-refined) evidence dict to merge into state.

The provider always returns a valid LogsEvidence — even on tool failure it
returns one with result=ERROR. So this node NEVER crashes the graph.
"""

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
from sre_agent.schemas import EvidenceResult, GraphState, LogsEvidence

log = get_logger("log_detective")


def log_detective(state: GraphState) -> dict[str, Any]:
    alert = state["alert"]
    provider = get_provider()
    started_at = alert.started_at
    window_from = started_at - timedelta(minutes=10)
    window_to = started_at + timedelta(minutes=5)

    log.info("log_detective.start", service=alert.service)

    # ── Step 1: structured fetch ──────────────────────────────────────
    try:
        if provider.name == "mock":
            ev = provider.fetch_logs(  # type: ignore[call-arg]
                service=alert.service,
                from_ts=window_from,
                to_ts=window_to,
                scenario_id=alert.scenario_id,
            )
        else:
            ev = provider.fetch_logs(
                service=alert.service,
                from_ts=window_from,
                to_ts=window_to,
            )
    except Exception as e:  # provider crashed unexpectedly
        log.exception("log_detective.fetch_failed", error=str(e))
        ev = LogsEvidence(
            result=EvidenceResult.ERROR,
            hits=0,
            interpretation=f"Logs API failed: {e}",
        )

    # ── Step 2: optional LLM refinement ───────────────────────────────
    if ev.result == EvidenceResult.FOUND:
        ev = _refine_with_llm(ev, alert.service)

    return {
        "logs": ev,
        "events": [
            make_event(
                "log-detective",
                "evidence",
                f"{ev.hits} log hits — {ev.interpretation}",
                result=ev.result.value,
            )
        ],
    }


def _refine_with_llm(ev: LogsEvidence, service: str) -> LogsEvidence:
    """Ask the LLM to write a sharper one-sentence interpretation."""
    try:
        persona, _sha = load_with_sha("log-detective")
        record_persona_load("log-detective", _sha)
        llm = get_chat_model(ModelRole.WORKER)
        top = ev.top_messages[0] if ev.top_messages else {}
        user = (
            f"Service: {service}\n"
            f"Total error hits: {ev.hits}\n"
            f"First seen: {ev.first_at}\n"
            f"Peak: {ev.peak_at}\n"
            f"Top message: {top.get('message', '(none)')} (count={top.get('count', 0)})\n\n"
            "Write ONE sentence (<200 chars) interpreting these logs for an on-call engineer. "
            "Focus on whether this looks like a single root cause or cascading failures. "
            "No preamble. Just the sentence."
        )
        with bind_agent("log-detective", prompt_sha=_sha):
            out = llm.invoke([SystemMessage(content=persona), HumanMessage(content=user)])
        text = (out.content or "").strip().split("\n")[0][:380]
        if text:
            return ev.model_copy(update={"interpretation": text})
    except Exception as e:
        log.warning("log_detective.llm_failed", error=str(e))
    return ev
