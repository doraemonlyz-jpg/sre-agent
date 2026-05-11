"""
The LangGraph orchestration definition.

Topology:

                ┌──────────────┐
                │ incident_pm  │  (open incident, emit event)
                └──────┬───────┘
                       │
            ┌──────────┼──────────┐──────────────┐
            ▼          ▼          ▼              ▼
       log_detec  metrics_an  trace_rdr    deploy_hist     (parallel)
            │          │          │              │
            └──────────┴──────────┴──────────────┘
                       │
                       ▼
              ┌──────────────────┐
              │ hypothesis_gen   │
              └─────────┬────────┘
                        ▼
              ┌──────────────────┐
              │ remediation_sug  │
              └─────────┬────────┘
                        ▼
              ┌──────────────────┐
              │     finalize     │  (write incident report, persist STATUS.json)
              └──────────────────┘
                        ▼
                       END

Production features baked in:
- SqliteSaver checkpointer → if the dashboard restarts mid-incident, the
  graph resumes from the last completed node.
- All evidence merges via the GraphState reducer.
- Conditional path: if hypothesis_gen produces NO_SIGNAL, we still go to
  remediation_sug (it emits an "investigate manually" plan).
"""

from __future__ import annotations

import os

# Tell LangGraph's msgpack serializer it's OK to deserialize our Pydantic types.
# Must be set BEFORE importing langgraph.* below.
_ALLOWED_MODULES = os.environ.get("LANGGRAPH_ALLOWED_MSGPACK_MODULES", "")
if "sre_agent.schemas" not in _ALLOWED_MODULES:
    os.environ["LANGGRAPH_ALLOWED_MSGPACK_MODULES"] = (
        f"{_ALLOWED_MODULES},sre_agent.schemas".strip(",")
    )

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

from sre_agent.logging import get_logger
from sre_agent.nodes import (
    deploy_historian,
    hypothesis_generator,
    incident_pm,
    log_detective,
    metrics_analyst,
    remediation_suggester,
    trace_reader,
)
from sre_agent.nodes._helpers import make_event
from sre_agent.schemas import GraphState, IncidentReport

log = get_logger("graph")


# ──────────────────────────────────────────────────────────────────────────
# Finalize node — writes the report to state.
# ──────────────────────────────────────────────────────────────────────────


def finalize(state: GraphState) -> dict[str, Any]:
    """
    Build the final IncidentReport. Determines phase based on whether we
    found anything.
    """
    alert = state["alert"]
    hyps = state.get("hypotheses")
    phase: str = "diagnosed"
    if hyps is None or not hyps.hypotheses:
        phase = "failed"
    elif hyps.top.confidence < 0.4:
        phase = "no_signal"

    report = IncidentReport(
        incident_id=f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        alert=alert,
        phase=phase,  # type: ignore[arg-type]
        started_at=alert.started_at,
        diagnosed_at=datetime.now(timezone.utc),
        logs=state.get("logs"),
        metrics=state.get("metrics"),
        traces=state.get("traces"),
        deploys=state.get("deploys"),
        hypotheses=hyps,
        remediation=state.get("remediation"),
    )

    return {
        "report": report,
        "events": [
            make_event(
                "finalize",
                "done",
                f"Incident {phase.upper()}: " + (
                    f"top={hyps.top.title} ({int(hyps.top.confidence*100)}%)"
                    if hyps and hyps.hypotheses
                    else "no diagnosis"
                ),
                phase=phase,
            )
        ],
    }


# ──────────────────────────────────────────────────────────────────────────
# Build the graph.
# ──────────────────────────────────────────────────────────────────────────


def build_graph(checkpointer=None):
    """
    Compile the LangGraph. Pass a custom checkpointer for tests; default is
    a SqliteSaver living under ./.state/.
    """
    builder = StateGraph(GraphState)

    builder.add_node("incident_pm", incident_pm)
    builder.add_node("log_detective", log_detective)
    builder.add_node("metrics_analyst", metrics_analyst)
    builder.add_node("trace_reader", trace_reader)
    builder.add_node("deploy_historian", deploy_historian)
    builder.add_node("hypothesis_generator", hypothesis_generator)
    builder.add_node("remediation_suggester", remediation_suggester)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "incident_pm")

    # parallel fan-out: PM → 4 workers
    for worker in ("log_detective", "metrics_analyst", "trace_reader", "deploy_historian"):
        builder.add_edge("incident_pm", worker)

    # fan-in: all 4 workers → hypothesis_generator
    # LangGraph's reducer (operator.add on `events`) merges the parallel branches.
    for worker in ("log_detective", "metrics_analyst", "trace_reader", "deploy_historian"):
        builder.add_edge(worker, "hypothesis_generator")

    builder.add_edge("hypothesis_generator", "remediation_suggester")
    builder.add_edge("remediation_suggester", "finalize")
    builder.add_edge("finalize", END)

    if checkpointer is None:
        checkpointer = _default_checkpointer()

    return builder.compile(checkpointer=checkpointer)


def _default_checkpointer():
    """SQLite checkpointer in ./.state/checkpoints.db (auto-created)."""
    backend = os.environ.get("SRE_CHECKPOINTER", "sqlite").lower()

    if backend == "postgres":
        # Postgres for production. Lazy import so dev doesn't need psycopg.
        from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore

        dsn = os.environ.get(
            "DATABASE_URL",
            "postgresql://sre:sre@localhost:5432/sre_agent",
        )
        saver = PostgresSaver.from_conn_string(dsn)
        saver.setup()
        return saver

    state_dir = Path(os.environ.get("SRE_STATE_DIR", ".state"))
    state_dir.mkdir(parents=True, exist_ok=True)
    db_path = state_dir / "checkpoints.db"

    # Long-lived sqlite3 connection — survives the function return.
    # `check_same_thread=False` is required because Flask (and tests) may invoke
    # the graph from different threads.
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)
