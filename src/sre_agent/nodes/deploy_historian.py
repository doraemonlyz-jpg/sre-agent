"""Deploy Historian node — finds suspicious deploys in the window."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from sre_agent.logging import get_logger
from sre_agent.models import ModelRole, get_chat_model
from sre_agent.nodes._helpers import make_event
from sre_agent.personas import load as load_persona
from sre_agent.providers import get_provider
from sre_agent.schemas import DeploysEvidence, EvidenceResult, GraphState

log = get_logger("deploy_historian")


def deploy_historian(state: GraphState) -> dict[str, Any]:
    alert = state["alert"]
    provider = get_provider()
    window_from = alert.started_at - timedelta(hours=2)
    window_to = alert.started_at

    log.info("deploy_historian.start", service=alert.service)

    # Include the affected service AND likely neighbours (we use a simple heuristic;
    # production would query a service-graph here).
    services = [alert.service] + _likely_neighbours(alert.service)

    try:
        if provider.name == "mock":
            ev = provider.fetch_deploys(  # type: ignore[call-arg]
                services=services,
                from_ts=window_from,
                to_ts=window_to,
                scenario_id=alert.scenario_id,
            )
        else:
            ev = provider.fetch_deploys(
                services=services,
                from_ts=window_from,
                to_ts=window_to,
            )
    except Exception as e:
        log.exception("deploy_historian.fetch_failed", error=str(e))
        ev = DeploysEvidence(
            result=EvidenceResult.ERROR,
            interpretation=f"Deploys API failed: {e}",
        )

    if ev.result == EvidenceResult.FOUND:
        ev = _refine_with_llm(ev, alert.service)

    return {
        "deploys": ev,
        "events": [
            make_event(
                "deploy-historian",
                "evidence",
                f"{len(ev.deploys)} deploy(s) — {ev.interpretation}",
                result=ev.result.value,
            )
        ],
    }


def _likely_neighbours(service: str) -> list[str]:
    """Cheap heuristic until we wire a real service graph."""
    suffixes = {"-api", "-service", "-svc"}
    for suf in suffixes:
        if service.endswith(suf):
            return ["payment-service", "search-service", "user-service"]
    return []


def _refine_with_llm(ev: DeploysEvidence, service: str) -> DeploysEvidence:
    try:
        persona = load_persona("deploy-historian")
        llm = get_chat_model(ModelRole.WORKER)
        lines = [
            f"- {d.service} {d.sha[:7]} @ {d.deployed_at} ({d.minutes_before:.0f}min before) "
            f"PR: {d.pr_title} by {d.author} | suspect={d.suspect}"
            for d in ev.deploys
        ]
        cfgs = "\n".join(f"- {c}" for c in ev.config_changes) or "(none)"
        user = (
            f"Affected service: {service}\n"
            f"Deploys found:\n" + "\n".join(lines) + "\n"
            f"Config changes:\n{cfgs}\n\n"
            "Write ONE sentence (<300 chars). Identify the single most-suspect change and why "
            "(timing, file paths, etc). No preamble."
        )
        out = llm.invoke([SystemMessage(content=persona), HumanMessage(content=user)])
        text = (out.content or "").strip().split("\n")[0][:380]
        if text:
            return ev.model_copy(update={"interpretation": text})
    except Exception as e:
        log.warning("deploy_historian.llm_failed", error=str(e))
    return ev
