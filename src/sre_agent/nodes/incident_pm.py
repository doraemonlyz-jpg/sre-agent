"""
Incident PM node — the entry orchestrator.

In v0 this used `sessions_send` to fan out. In LangGraph the fan-out is
expressed as edges, not in code. So this node's job is small:

1. Stamp the incident_id and `started_at`.
2. Emit a "investigation started" event for the UI.
3. Return — the graph then fans out to the 4 parallel workers automatically.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sre_agent.logging import get_logger
from sre_agent.nodes._helpers import make_event
from sre_agent.schemas import GraphState

log = get_logger("incident_pm")


def incident_pm(state: GraphState) -> dict[str, Any]:
    alert = state["alert"]
    log.info("incident_pm.start", service=alert.service, severity=alert.severity)

    return {
        "events": [
            make_event(
                "incident-pm",
                "started",
                f"Incident opened for {alert.service} ({alert.severity.value}). "
                f"Dispatching parallel investigators.",
                incident_id=f"INC-{uuid4().hex[:8].upper()}",
                started_at=datetime.now(timezone.utc).isoformat(),
            )
        ],
    }
