"""
SRE Command Center — Flask dashboard for the multi-agent incident-response system.

v1 (this file): the dashboard spawns **real LangGraph runs** in a background
thread. Each run produces a typed `IncidentReport`. We expose:

  GET  /                                 serves the UI (index.html)
  GET  /api/scenarios                    list available scenarios
  POST /api/incidents/fire               fire a (mock) alert -> spawns LangGraph
  GET  /api/incidents                    list all incidents
  GET  /api/incidents/<id>               full incident state (legacy-compatible)
  GET  /api/incidents/<id>/report        the typed Pydantic IncidentReport
  POST /api/incidents/<id>/post-slack    (stub) Slack preview
  GET  /api/health                       health probe
  POST /api/sre/datadog/*                mock Datadog endpoints (kept for back-compat)
  POST /api/sre/deploys                  mock deploys endpoint

The frontend treats the dashboard as a thin shell — it polls `/api/incidents/<id>`.
The polling response shape is unchanged from v0 (`findings.{logs,metrics,...}`,
`hypothesis`, `remediation`) so the existing `app.js` keeps working.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from sre_agent.graph import build_graph
from sre_agent.logging import setup_logging
from sre_agent.providers.mock import MockProvider
from sre_agent.schemas import AlertIn, GraphState, IncidentReport, Severity

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

setup_logging()
logger = logging.getLogger("sre_agent.dashboard")

PORT = int(os.environ.get("SRE_DASHBOARD_PORT") or os.environ.get("SRE_PORT", "5060"))
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INCIDENTS_DIR = Path.home() / ".sre-agent" / "incidents"
INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)

# Single graph instance — checkpointer keeps state across runs.
_GRAPH = build_graph()
_MOCK_PROVIDER = MockProvider()

# ---------------------------------------------------------------------------
# In-memory incident store. State lives in two places:
# 1. LangGraph's checkpointer (durable, source of truth)
# 2. This in-memory dict (UI-friendly, fast to read, legacy shape)
# ---------------------------------------------------------------------------

INCIDENTS: dict[str, dict[str, Any]] = {}
INCIDENTS_LOCK = threading.Lock()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _persist(incident_id: str) -> None:
    inc = INCIDENTS.get(incident_id)
    if not inc:
        return
    folder = INCIDENTS_DIR / incident_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "INCIDENT.json").write_text(json.dumps(inc, indent=2, default=str))


def _push_event(incident_id: str, ev: dict[str, Any]) -> None:
    """Append a typed event from the graph to the UI's feed."""
    with INCIDENTS_LOCK:
        inc = INCIDENTS.get(incident_id)
        if inc is None:
            return
        inc["events"].append(
            {
                "ts": _ts_to_ms(ev.get("ts")),
                "agent": ev.get("agent", "?"),
                "action": ev.get("kind", "?"),
                "detail": ev.get("message", ""),
            }
        )


def _ts_to_ms(ts: str | None) -> int:
    """Convert an ISO timestamp string to ms-since-epoch (for the UI)."""
    if not ts:
        return _now_ms()
    try:
        return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return _now_ms()


# ---------------------------------------------------------------------------
# Legacy-shape adapters (so frontend doesn't need to change)
# ---------------------------------------------------------------------------


def _evidence_to_legacy(report: IncidentReport) -> dict[str, Any]:
    """Map the typed report back to the v0 'findings' shape the UI knows."""
    findings: dict[str, Any] = {}

    if report.logs:
        findings["logs"] = {
            "hits": report.logs.hits,
            "first_at": str(report.logs.first_at) if report.logs.first_at else None,
            "peak_at": str(report.logs.peak_at) if report.logs.peak_at else None,
            "top_messages": report.logs.top_messages,
            "samples": [],
            "interpretation": report.logs.interpretation,
        }

    if report.metrics:
        findings["metrics"] = {
            m.name: {
                "baseline": m.baseline,
                "peak": m.peak,
                "peak_at": str(m.peak_at) if m.peak_at else None,
                "verdict": m.verdict,
            }
            for m in report.metrics.metrics
        }

    if report.traces:
        findings["traces"] = {
            "traces_inspected": report.traces.traces_inspected,
            "error_rate": report.traces.error_rate,
            "hot_span": report.traces.hot_span.model_dump() if report.traces.hot_span else None,
            "downstream_suspect": report.traces.downstream_suspect,
        }

    if report.deploys:
        findings["deploys"] = {
            "deploys": [d.model_dump(mode="json") for d in report.deploys.deploys],
            "config_changes": report.deploys.config_changes,
        }

    return findings


def _hypothesis_to_legacy(report: IncidentReport) -> dict[str, Any] | None:
    if not report.hypotheses or not report.hypotheses.hypotheses:
        return None
    top = report.hypotheses.top
    return {
        "top": f"{top.title} — {top.detail}",
        "confidence": top.confidence,
        "supporting_evidence": top.supporting_evidence,
        "alternative": (
            f"{report.hypotheses.hypotheses[1].title}"
            if len(report.hypotheses.hypotheses) > 1
            else "(no alternative)"
        ),
        "why_not_alternative": top.why_not_alternative,
    }


def _remediation_to_legacy(report: IncidentReport) -> list[dict[str, Any]]:
    if not report.remediation:
        return []
    return [
        {
            "step": i,
            "title": a.title,
            "command": a.command,
            "why": a.why,
            "expected_effect": a.expected_effect,
            "reversal": a.reversal,
            "risk": a.risk.value,
        }
        for i, a in enumerate(report.remediation.actions, 1)
    ]


# ---------------------------------------------------------------------------
# The actual pipeline runner — replaces v0's `_simulate_pipeline`.
# ---------------------------------------------------------------------------


def _run_pipeline(incident_id: str, alert: AlertIn) -> None:
    """
    Stream the LangGraph run. Each chunk's `events` go to the UI feed; the
    final state is persisted. Exceptions are caught so a broken LLM doesn't
    crash the Flask app.
    """
    started_at = _now_ms()
    config = {"configurable": {"thread_id": incident_id}}
    initial: GraphState = {"alert": alert, "events": []}

    try:
        for chunk in _GRAPH.stream(initial, config=config):
            for _node_name, partial in chunk.items():
                for ev in partial.get("events", []) or []:
                    _push_event(incident_id, ev)

        # Pull final state from checkpointer
        state = _GRAPH.get_state(config).values
        report: IncidentReport | None = state.get("report")
        if report is None:
            raise RuntimeError("graph completed without producing a report")

        finished_at = _now_ms()
        with INCIDENTS_LOCK:
            inc = INCIDENTS[incident_id]
            inc["phase"] = report.phase
            inc["diagnosed_at"] = finished_at
            inc["diagnosis_ms"] = finished_at - started_at
            inc["findings"] = _evidence_to_legacy(report)
            inc["hypothesis"] = _hypothesis_to_legacy(report)
            inc["remediation"] = _remediation_to_legacy(report)
            inc["report_json"] = report.model_dump(mode="json", exclude_none=True)
        _persist(incident_id)

    except Exception as e:
        logger.exception("pipeline failed for incident %s", incident_id)
        finished_at = _now_ms()
        with INCIDENTS_LOCK:
            inc = INCIDENTS.get(incident_id) or {}
            inc["phase"] = "failed"
            inc["diagnosed_at"] = finished_at
            inc["diagnosis_ms"] = finished_at - started_at
            inc["error"] = str(e)
            inc["events"].append(
                {
                    "ts": finished_at,
                    "agent": "system",
                    "action": "error",
                    "detail": f"pipeline crashed: {e}",
                }
            )
        _persist(incident_id)


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder=None)


@app.route("/")
def root():
    return send_from_directory(str(HERE), "index.html")


@app.route("/<path:fname>")
def static_files(fname: str):
    safe = (HERE / fname).resolve()
    if not str(safe).startswith(str(HERE)):
        return "forbidden", 403
    if safe.is_file():
        return send_from_directory(str(HERE), fname)
    return "not found", 404


# ---- scenarios / incidents -----------------------------------------------


@app.route("/api/scenarios", methods=["GET"])
def api_scenarios():
    items = []
    for s in _MOCK_PROVIDER.list_scenarios():
        seed = _MOCK_PROVIDER.get_scenario_alert(s["id"])
        items.append(
            {
                "id": s["id"],
                "label": s["label"],
                "service": s["service"],
                "severity": seed["severity"],
            }
        )
    return jsonify({"scenarios": items})


@app.route("/api/incidents/fire", methods=["POST"])
def api_fire():
    payload = request.get_json(force=True, silent=True) or {}
    scenario_id = payload.get("scenario_id")

    if scenario_id:
        try:
            seed = _MOCK_PROVIDER.get_scenario_alert(scenario_id)
        except KeyError:
            return jsonify({"error": f"unknown scenario_id: {scenario_id}"}), 400
        alert = AlertIn(
            service=seed["service"],
            severity=Severity(seed["severity"]),
            description=seed["description"],
            started_at=seed.get("started_at") or datetime.now(timezone.utc),
            tags=seed.get("tags", []),
            scenario_id=scenario_id,
        )
    else:
        # custom alert from request body
        try:
            alert = AlertIn(
                service=payload["service"],
                severity=Severity(payload.get("severity", "SEV-2")),
                description=payload["description"],
                started_at=datetime.now(timezone.utc),
                tags=payload.get("tags", []),
            )
        except (KeyError, ValueError) as e:
            return jsonify({"error": f"bad alert payload: {e}"}), 400

    incident_id = uuid.uuid4().hex[:10]

    with INCIDENTS_LOCK:
        INCIDENTS[incident_id] = {
            "id": incident_id,
            "scenario_id": scenario_id,
            "alert": alert.model_dump(mode="json"),
            "phase": "investigating",
            "started_at": _now_ms(),
            "events": [],
            "findings": {},
            "hypothesis": None,
            "remediation": None,
        }
    _persist(incident_id)

    threading.Thread(
        target=_run_pipeline, args=(incident_id, alert), daemon=True
    ).start()

    return jsonify({"id": incident_id, "phase": "investigating"})


@app.route("/api/incidents", methods=["GET"])
def api_list_incidents():
    with INCIDENTS_LOCK:
        items = sorted(
            (
                {
                    "id": i["id"],
                    "alert": i["alert"],
                    "phase": i["phase"],
                    "started_at": i["started_at"],
                    "diagnosed_at": i.get("diagnosed_at"),
                    "diagnosis_ms": i.get("diagnosis_ms"),
                }
                for i in INCIDENTS.values()
            ),
            key=lambda x: -x["started_at"],
        )
    return jsonify({"incidents": items})


@app.route("/api/incidents/<incident_id>", methods=["GET"])
def api_get_incident(incident_id: str):
    with INCIDENTS_LOCK:
        inc = INCIDENTS.get(incident_id)
        if not inc:
            return jsonify({"error": "not found"}), 404
        return jsonify(inc)


@app.route("/api/incidents/<incident_id>/report", methods=["GET"])
def api_get_incident_report(incident_id: str):
    """Returns the strict, typed Pydantic IncidentReport — for tooling/API consumers."""
    with INCIDENTS_LOCK:
        inc = INCIDENTS.get(incident_id)
        if not inc:
            return jsonify({"error": "not found"}), 404
        report = inc.get("report_json")
        if not report:
            return jsonify({"error": "still investigating"}), 409
        return jsonify(report)


@app.route("/api/incidents/<incident_id>/post-slack", methods=["POST"])
def api_post_slack(incident_id: str):
    with INCIDENTS_LOCK:
        inc = INCIDENTS.get(incident_id)
        if not inc or not inc.get("hypothesis"):
            return jsonify({"error": "not diagnosed yet"}), 400
    return jsonify(
        {
            "ok": True,
            "note": "v1 stub — set SLACK_WEBHOOK_URL to enable real posting",
            "preview": _slack_preview(inc),
        }
    )


def _slack_preview(inc: dict[str, Any]) -> str:
    h = inc["hypothesis"]
    return (
        f"🚨 *{inc['alert']['service']}* {inc['alert']['severity']}\n"
        f"_{inc['alert']['description']}_\n\n"
        f"*Top hypothesis* ({int(h['confidence']*100)}%):\n"
        f"> {h['top']}\n\n"
        f"*Diagnosed in*: {inc.get('diagnosis_ms', 0)/1000:.1f}s\n"
        f"*Remediation*: {len(inc.get('remediation') or [])} actions ranked — see dashboard"
    )


# ---- mock data APIs (kept for back-compat / debugging) -------------------


def _scenario_for_service(service: str) -> dict[str, Any] | None:
    """Legacy lookup used by the mock endpoints below."""
    for sid in _MOCK_PROVIDER._scenarios:
        s = _MOCK_PROVIDER._scenarios[sid]
        if s["alert"]["service"] == service:
            return s
    return None


@app.route("/api/sre/datadog/logs", methods=["POST"])
def api_dd_logs():
    body = request.get_json(force=True, silent=True) or {}
    scen = _scenario_for_service(body.get("service", ""))
    return jsonify(scen["logs"] if scen else {"hits": 0, "samples": []})


@app.route("/api/sre/datadog/metrics", methods=["POST"])
def api_dd_metrics():
    body = request.get_json(force=True, silent=True) or {}
    scen = _scenario_for_service(body.get("service", ""))
    if not scen:
        return jsonify({})
    metric = body.get("metric")
    if metric:
        return jsonify(scen["metrics"].get(metric, {}))
    return jsonify(scen["metrics"])


@app.route("/api/sre/datadog/traces", methods=["POST"])
def api_dd_traces():
    body = request.get_json(force=True, silent=True) or {}
    scen = _scenario_for_service(body.get("service", ""))
    return jsonify(scen["traces"] if scen else {"traces_inspected": 0, "sample_trace_ids": []})


@app.route("/api/sre/deploys", methods=["POST"])
def api_deploys():
    body = request.get_json(force=True, silent=True) or {}
    for svc in body.get("services") or []:
        scen = _scenario_for_service(svc)
        if scen:
            return jsonify(scen["deploys"])
    return jsonify({"deploys": [], "config_changes": []})


# ---- health --------------------------------------------------------------


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify(
        {
            "ok": True,
            "scenarios": len(_MOCK_PROVIDER.list_scenarios()),
            "active_incidents": sum(
                1 for i in INCIDENTS.values() if i["phase"] == "investigating"
            ),
            "total_incidents": len(INCIDENTS),
            "checkpointer": os.environ.get("SRE_CHECKPOINTER", "sqlite"),
            "llm_provider": os.environ.get("SRE_LLM_PROVIDER") or "auto",
        }
    )


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"SRE Command Center on http://127.0.0.1:{PORT}")
    print(f"   {len(_MOCK_PROVIDER.list_scenarios())} demo scenarios loaded")
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)
