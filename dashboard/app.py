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

from sre_agent.auth import auth_required as _auth_required_flag
from sre_agent.auth import require_scope
from sre_agent.cache import CACHE
from sre_agent.cache import store as cache_store
from sre_agent.cache import try_get as cache_try_get
from sre_agent.calibration import IsotonicCalibrator
from sre_agent.feedback import STORE as FEEDBACK_STORE
from sre_agent.feedback import make_record as make_feedback_record
from sre_agent.graph import build_graph
from sre_agent.harness import RECORDER, bind_incident
from sre_agent.logging import setup_logging
from sre_agent.notifications import SlackNotifier
from sre_agent.observability import (
    EXPORTER as OBSERVABILITY_EXPORTER,
)
from sre_agent.providers.mock import MockProvider
from sre_agent.ratelimit import LIMITER
from sre_agent.ratelimit import require as require_rate_limit
from sre_agent.scale import COUNTERS, classify_tier, submit_job
from sre_agent.schemas import AlertIn, GraphState, IncidentReport, Severity
from sre_agent.webhooks import UnknownPayloadError, parse_alert

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

setup_logging()
logger = logging.getLogger("sre_agent.dashboard")

# NOTE: avoid port 5060 — Chrome/Firefox blacklist it (SIP/VoIP), browsers
# return ERR_UNSAFE_PORT. 5080 is in the safe range.
PORT = int(os.environ.get("SRE_DASHBOARD_PORT") or os.environ.get("SRE_PORT", "5080"))
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


# ---------------------------------------------------------------------------
# Confidence calibrator (L6.3)
#
# Loaded once at module import. Safe to ship missing: `IsotonicCalibrator.load`
# returns the identity calibrator on missing/corrupt files, so the dashboard
# boots cleanly in environments that haven't run `sre-agent calibrate` yet.
#
# `SRE_CALIBRATOR_PATH` env var lets ops override the artifact location
# (e.g. mount a per-deploy calibrator into the container).
# ---------------------------------------------------------------------------

_CALIBRATOR_PATH = Path(
    os.environ.get("SRE_CALIBRATOR_PATH")
    or (ROOT / "data" / "calibrator.json")
)
CALIBRATOR = IsotonicCalibrator.load(_CALIBRATOR_PATH)


def _apply_calibrator_to_incident(inc: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of `inc` with hypothesis.confidence calibrated.

    The raw value is preserved under `hypothesis.confidence_raw` so the
    UI can show "85% raw -> 64% calibrated" for transparency. If the
    calibrator is identity (the default before anyone runs `sre-agent
    calibrate`), this function is a no-op.
    """
    if CALIBRATOR.is_identity:
        return inc
    hyp = inc.get("hypothesis")
    if not hyp:
        return inc
    raw = hyp.get("confidence")
    if not isinstance(raw, (int, float)):
        return inc
    if not (0.0 <= float(raw) <= 1.0):
        return inc
    out = dict(inc)
    out_hyp = dict(hyp)
    out_hyp["confidence_raw"] = float(raw)
    out_hyp["confidence"] = round(CALIBRATOR.apply(float(raw)), 4)
    out_hyp["calibrated"] = True
    out["hypothesis"] = out_hyp
    return out


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

    if report.runbooks:
        findings["runbooks"] = {
            "result": report.runbooks.result.value,
            "library_size": report.runbooks.library_size,
            "backend": report.runbooks.backend,
            "interpretation": report.runbooks.interpretation,
            "hits": [h.model_dump(mode="json") for h in report.runbooks.hits],
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

    `bind_incident(incident_id)` tags every LLM call made inside this
    block with our domain identifier, so the harness ring buffer can
    return "all calls for incident X" via `/api/incidents/<id>/calls`.
    """
    started_at = _now_ms()
    config = {"configurable": {"thread_id": incident_id}}
    initial: GraphState = {"alert": alert, "events": []}

    try:
        with bind_incident(incident_id):
            for chunk in _GRAPH.stream(initial, config=config):
                for _node_name, partial in chunk.items():
                    for ev in partial.get("events", []) or []:
                        _push_event(incident_id, ev)

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
        # Stash a compact snapshot in the response cache so identical
        # alerts in the next SRE_CACHE_TTL_SECONDS skip the full pipeline.
        # Failed runs intentionally don't go into the cache.
        try:
            with INCIDENTS_LOCK:
                snapshot = {
                    "phase": INCIDENTS[incident_id]["phase"],
                    "findings": INCIDENTS[incident_id].get("findings", {}),
                    "hypothesis": INCIDENTS[incident_id].get("hypothesis"),
                    "remediation": INCIDENTS[incident_id].get("remediation"),
                    "report_json": INCIDENTS[incident_id].get("report_json"),
                    "diagnosis_ms": INCIDENTS[incident_id].get("diagnosis_ms"),
                }
            cache_store(
                alert.service,
                alert.severity.value,
                alert.description,
                incident_id,
                snapshot,
            )
        except Exception:
            logger.exception("cache.store_failed for %s", incident_id)

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


def _spawn_incident(alert: AlertIn, *, scenario_id: str | None = None) -> str:
    """Register an incident, persist, and kick off the LangGraph run.

    Harness L4 — response cache: if an identical alert was diagnosed in the
    last `SRE_CACHE_TTL_SECONDS`, materialize a *new* incident_id pointing
    at the cached findings. This protects us from misconfigured alert
    rules that re-fire every 30s, and is the in-process mock of an
    upstream Redis/Memcached.
    """
    incident_id = uuid.uuid4().hex[:10]
    cached = cache_try_get(alert.service, alert.severity.value, alert.description)
    tier = classify_tier(
        severity=alert.severity.value,
        description=alert.description,
        scenario_id=scenario_id,
    )

    if cached is not None:
        cached_id, payload = cached
        now = _now_ms()
        with INCIDENTS_LOCK:
            INCIDENTS[incident_id] = {
                "id": incident_id,
                "scenario_id": scenario_id,
                "alert": alert.model_dump(mode="json"),
                "phase": payload.get("phase", "diagnosed"),
                "started_at": now,
                "diagnosed_at": now,
                "diagnosis_ms": 0,
                "events": [
                    {
                        "ts": now,
                        "agent": "harness",
                        "action": "cache_hit",
                        "detail": (
                            f"reused diagnosis from incident {cached_id} "
                            f"(SRE_CACHE_TTL_SECONDS = {int(_cache_ttl())}s)"
                        ),
                    }
                ],
                "findings": payload.get("findings", {}),
                "hypothesis": payload.get("hypothesis"),
                "remediation": payload.get("remediation"),
                "report_json": payload.get("report_json"),
                "model_tier": "rule",  # cache hit costs no LLM, so it's a "rule"-tier conclusion
                "served_from_cache": True,
                "cache_origin_incident_id": cached_id,
            }
        _persist(incident_id)
        return incident_id

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
            "model_tier": tier,
            "served_from_cache": False,
        }
    _persist(incident_id)
    submit_job(_run_pipeline, incident_id, alert, tier=tier)
    return incident_id


def _cache_ttl() -> float:
    try:
        return float(os.environ.get("SRE_CACHE_TTL_SECONDS", "300"))
    except ValueError:
        return 300.0


@app.route("/api/incidents/fire", methods=["POST"])
@require_scope("fire")
@require_rate_limit("fire")
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

    incident_id = _spawn_incident(alert, scenario_id=scenario_id)
    return jsonify({"id": incident_id, "phase": "investigating"})


@app.route("/api/alerts/webhook", methods=["POST"])
@require_rate_limit("webhook")
def api_alerts_webhook():
    """
    Real-world ingestion endpoint. Accepts payloads from:

      * Datadog Monitor → Webhook (auto-detected)
      * PagerDuty Webhook v3       (auto-detected)
      * Generic JSON               ({service, description, ...})

    Override with ?source=datadog|pagerduty|generic or `X-SRE-Source`
    header. Optional shared-secret auth: set SRE_WEBHOOK_SECRET in env
    and have the sender include it in `X-SRE-Token`.
    """
    expected_secret = os.environ.get("SRE_WEBHOOK_SECRET")
    if expected_secret:
        provided = request.headers.get("X-SRE-Token", "")
        if provided != expected_secret:
            return jsonify({"error": "invalid or missing X-SRE-Token"}), 401

    payload = request.get_json(force=True, silent=True) or {}
    source = (
        request.args.get("source")
        or request.headers.get("X-SRE-Source")
    )
    try:
        alert = parse_alert(payload, source=source)
    except UnknownPayloadError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # pragma: no cover — schema validation
        return jsonify({"error": f"bad alert payload: {e}"}), 400

    incident_id = _spawn_incident(alert)
    return jsonify({"id": incident_id, "phase": "investigating", "source": source or "auto"})


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
                    "model_tier": i.get("model_tier", "cheap"),
                    "served_from_cache": i.get("served_from_cache", False),
                    "cache_origin_incident_id": i.get("cache_origin_incident_id"),
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
        # Apply the fitted calibrator (L6.3) before surfacing confidence
        # to oncall. No-op when no calibrator has been fitted yet --
        # the dashboard ships boot-safe with the identity calibrator.
        return jsonify(_apply_calibrator_to_incident(inc))


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
        # Copy so we don't hold the lock across the HTTP call.
        snapshot = dict(inc)

    notifier = SlackNotifier.from_env()
    try:
        result = notifier.post_incident(snapshot)
    finally:
        notifier.close()

    return jsonify(
        {
            "ok": result.sent or result.dry_run,
            "sent": result.sent,
            "dry_run": result.dry_run,
            "status": result.status,
            "error": result.error,
            "preview": result.preview,
            "payload": result.payload,
        }
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


# ---- Phase E: production-scale mock --------------------------------------


@app.route("/api/scale/stats", methods=["GET"])
def api_scale_stats():
    """
    Live snapshot of the bounded worker pool + tier breakdown +
    rolling LLM call rate. Surfaced as the "Scale" strip in the UI;
    `watch -n1 curl localhost:5080/api/scale/stats` for the CLI version.
    """
    snap = COUNTERS.snapshot()
    snap["max_concurrent"] = int(
        os.environ.get(
            "SRE_MAX_CONCURRENT_INVESTIGATIONS",
            os.environ.get("SRE_MAX_CONCURRENT", "4"),
        )
    )
    # Derived: cost saved by tier routing (vs. naively running every
    # incident through premium). Numbers are illustrative; in prod you'd
    # plug real per-tier $/call.
    tier_costs = {"rule": 0.0, "cheap": 0.0008, "premium": 0.05}
    by_tier = snap["by_tier_completed"]
    actual = sum(tier_costs[t] * by_tier.get(t, 0) for t in tier_costs)
    if_all_premium = tier_costs["premium"] * snap["completed_total"]
    snap["cost_estimate_usd"] = round(actual, 4)
    snap["cost_if_all_premium_usd"] = round(if_all_premium, 4)
    snap["cost_saved_usd"] = round(max(0.0, if_all_premium - actual), 4)
    return jsonify(snap)


@app.route("/api/incidents/burst", methods=["POST"])
@require_scope("burst")
@require_rate_limit("burst")
def api_burst():
    """
    Fire N synthetic alerts at once to demonstrate burst handling. This
    is the in-process mock of "1000 alerts hit Kafka when a hub service
    dies" — beyond `SRE_MAX_CONCURRENT_INVESTIGATIONS`, the rest queue
    up and process in batches.

    Query / body params:
      n             how many alerts to fire (default 50, max 500)
      scenario_id   which scenario to clone (default 'redis-pool-exhaustion')
      service       override the service name (default: scenario's service)
      severity      override the severity (default: scenario's severity)
    """
    payload = request.get_json(force=True, silent=True) or {}
    n = int(payload.get("n") or request.args.get("n", 50))
    n = max(1, min(500, n))
    scenario_id = (
        payload.get("scenario_id")
        or request.args.get("scenario_id")
        or "redis-pool-exhaustion"
    )
    try:
        seed = _MOCK_PROVIDER.get_scenario_alert(scenario_id)
    except KeyError:
        return jsonify({"error": f"unknown scenario_id: {scenario_id}"}), 400

    service = payload.get("service") or request.args.get("service") or seed["service"]
    severity = payload.get("severity") or request.args.get("severity") or seed["severity"]

    ids: list[str] = []
    base_desc = seed["description"]
    for i in range(n):
        alert = AlertIn(
            service=service,
            severity=Severity(severity),
            description=f"{base_desc} (burst #{i+1}/{n})",
            started_at=datetime.now(timezone.utc),
            tags=list(seed.get("tags", [])),
            scenario_id=scenario_id,
        )
        ids.append(_spawn_incident(alert, scenario_id=scenario_id))

    return jsonify(
        {
            "burst": True,
            "queued": n,
            "incident_ids": ids,
            "max_concurrent": int(
                os.environ.get(
                    "SRE_MAX_CONCURRENT_INVESTIGATIONS",
                    os.environ.get("SRE_MAX_CONCURRENT", "4"),
                )
            ),
            "note": (
                "All alerts submitted to the bounded worker pool. "
                "Poll /api/scale/stats to watch queue depth drain."
            ),
        }
    )


# ---- Harness (L3/L4) -----------------------------------------------------


@app.route("/api/harness/summary", methods=["GET"])
def api_harness_summary():
    """Aggregate stats over the harness ring buffer + response cache."""
    return jsonify(
        {
            "recorder": RECORDER.summary(),
            "cache": CACHE.stats(),
            "rate_limit": LIMITER.stats(),
            "feedback": FEEDBACK_STORE.summary(),
            "observability": OBSERVABILITY_EXPORTER.stats(),
            "calibration": {
                "loaded_from": str(_CALIBRATOR_PATH),
                "is_identity": CALIBRATOR.is_identity,
                "n_train": CALIBRATOR.n_train,
                "ece_before": round(CALIBRATOR.fit_ece_before, 4),
                "ece_after": round(CALIBRATOR.fit_ece_after, 4),
                "brier_before": round(CALIBRATOR.fit_brier_before, 4),
                "brier_after": round(CALIBRATOR.fit_brier_after, 4),
                "n_breakpoints": len(CALIBRATOR.breakpoints),
            },
        }
    )


@app.route("/api/harness/calibration", methods=["GET"])
def api_harness_calibration():
    """The currently loaded calibrator's breakpoints + diagnostics.

    Used by ops to confirm "what is the dashboard ACTUALLY applying to
    confidence numbers right now". Especially valuable after a deploy:
    rolling out a stale calibrator silently is exactly the failure mode
    a calibration system is supposed to prevent.
    """
    return jsonify(
        {
            "loaded_from": str(_CALIBRATOR_PATH),
            "calibrator": CALIBRATOR.to_dict(),
        }
    )


@app.route("/api/harness/calls", methods=["GET"])
def api_harness_calls():
    """
    Recent harness records (LLM calls, persona loads, cache events, retries).
    Filter with ?kind=llm_call|cache_hit|cache_miss|persona_load|retry and
    ?limit=N (default 50, max 500).
    """
    kind = request.args.get("kind")
    try:
        limit = max(1, min(500, int(request.args.get("limit", "50"))))
    except ValueError:
        limit = 50
    recs = RECORDER.recent(limit=limit, kind=kind)  # type: ignore[arg-type]
    return jsonify({"records": [r.to_json() for r in recs]})


@app.route("/api/incidents/<incident_id>/calls", methods=["GET"])
def api_incident_calls(incident_id: str):
    """Every harness record tagged with this incident_id."""
    with INCIDENTS_LOCK:
        exists = incident_id in INCIDENTS
    if not exists:
        return jsonify({"error": "unknown incident"}), 404
    recs = RECORDER.for_incident(incident_id)
    by_agent: dict[str, int] = {}
    prompt_shas: dict[str, str] = {}
    for r in recs:
        by_agent[r.agent] = by_agent.get(r.agent, 0) + 1
        if r.prompt_sha and r.agent not in prompt_shas:
            prompt_shas[r.agent] = r.prompt_sha
    return jsonify(
        {
            "incident_id": incident_id,
            "n_records": len(recs),
            "by_agent": by_agent,
            "prompt_shas": prompt_shas,
            "records": [r.to_json() for r in recs],
        }
    )


# ---- Feedback (L5 flywheel) ----------------------------------------------


@app.route("/api/incidents/<incident_id>/feedback", methods=["POST"])
@require_scope("feedback")
@require_rate_limit("feedback")
def api_post_feedback(incident_id: str):
    """
    Capture oncall feedback on an incident's diagnosis. This is the
    substrate for the L5 flywheel: every record points at a specific
    incident + the prompt SHAs that produced it, so we can later group
    "where did this prompt mislead the oncall?"
    """
    with INCIDENTS_LOCK:
        inc = INCIDENTS.get(incident_id)
    if not inc:
        return jsonify({"error": f"unknown incident {incident_id}"}), 404

    payload = request.get_json(force=True, silent=True) or {}
    try:
        # Grab the prompt SHAs that were used for this incident so the
        # feedback record is self-contained for offline analysis.
        recs = RECORDER.for_incident(incident_id)
        prompt_shas: dict[str, str] = {}
        for r in recs:
            if r.prompt_sha and r.agent not in prompt_shas:
                prompt_shas[r.agent] = r.prompt_sha

        # Submitter — prefer auth token name, then payload override, else anon.
        from flask import g

        tok = getattr(g, "auth_token", None)
        submitter = (
            (payload.get("submitter") or "").strip()
            or (tok.name if tok is not None else "anon")
        )

        # We persist the RAW (pre-calibration) confidence so calibration
        # remains a self-contained pre/post analysis -- otherwise the
        # calibrator would be evaluating its own output.
        _hyp = inc.get("hypothesis") or {}
        _conf = _hyp.get("confidence_raw")
        if _conf is None:
            _conf = _hyp.get("confidence")
        rec = make_feedback_record(
            verdict=payload.get("verdict", "thumbs_up"),
            submitter=submitter,
            rating=payload.get("rating"),
            correct_root_cause=payload.get("correct_root_cause"),
            correct_remediation=payload.get("correct_remediation"),
            free_text=payload.get("free_text"),
            agent_root_cause=_hyp.get("top"),
            agent_confidence=float(_conf) if isinstance(_conf, (int, float)) else None,
            prompt_shas_seen=prompt_shas,
            tags=payload.get("tags") or [],
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    FEEDBACK_STORE.append(incident_id, rec, alert=inc.get("alert"))
    return jsonify({"ok": True, "feedback_id": rec.id}), 201


@app.route("/api/incidents/<incident_id>/feedback", methods=["GET"])
def api_get_feedback(incident_id: str):
    """Return every feedback record for this incident, or 404."""
    blob = FEEDBACK_STORE.get(incident_id)
    if blob is None:
        return jsonify({"records": [], "incident_id": incident_id})
    return jsonify(blob)


@app.route("/api/feedback/summary", methods=["GET"])
def api_feedback_summary():
    """Aggregate counts + CSAT for the dashboard. Returns 0s when empty."""
    return jsonify(FEEDBACK_STORE.summary())


@app.route("/api/feedback/recent", methods=["GET"])
def api_feedback_recent():
    """Last 50 incidents that received feedback. For an L5 'review queue'."""
    try:
        limit = max(1, min(200, int(request.args.get("limit", "50"))))
    except ValueError:
        limit = 50
    return jsonify({"incidents": FEEDBACK_STORE.list_recent(limit)})


@app.route("/api/slack/actions", methods=["POST"])
@require_rate_limit("feedback")
def api_slack_actions():
    """
    Slack interactive endpoint. The Block Kit buttons in our message
    POST here with X-Slack-Signature; we verify the HMAC, parse the
    action, and translate to a feedback record.

    Set SLACK_SIGNING_SECRET in env. Set SRE_SLACK_VERIFY_REQUIRED=1
    in prod to enforce verification (default off so curl-driven tests
    work).
    """
    from sre_agent.slack_actions import (
        SlackActionError,
        parse_payload,
        verify_required,
        verify_signature,
    )

    # cache=True so request.form can re-parse the body after we read it.
    body = request.get_data(cache=True) or b""
    if verify_required():
        ok = verify_signature(
            body=body,
            timestamp=request.headers.get("X-Slack-Request-Timestamp", ""),
            signature=request.headers.get("X-Slack-Signature", ""),
        )
        if not ok:
            return jsonify({"error": "slack signature verification failed"}), 401

    try:
        action = parse_payload(request.form)
    except SlackActionError as e:
        return jsonify({"error": str(e)}), 400

    with INCIDENTS_LOCK:
        if action.incident_id not in INCIDENTS:
            return jsonify({"error": f"unknown incident {action.incident_id}"}), 404

    recs = RECORDER.for_incident(action.incident_id)
    prompt_shas = {r.agent: r.prompt_sha for r in recs if r.prompt_sha}

    with INCIDENTS_LOCK:
        _inc_snapshot = INCIDENTS.get(action.incident_id) or {}
        _alert_snapshot = _inc_snapshot.get("alert")
        _hyp_snapshot = _inc_snapshot.get("hypothesis") or {}
        _agent_rc = _hyp_snapshot.get("top")
        _agent_conf = _hyp_snapshot.get("confidence_raw") or _hyp_snapshot.get("confidence")
    rec = make_feedback_record(
        verdict=action.verdict,
        submitter=f"slack:{action.user_name}",
        tags=action.tags,
        agent_root_cause=_agent_rc,
        agent_confidence=float(_agent_conf) if isinstance(_agent_conf, (int, float)) else None,
        prompt_shas_seen=prompt_shas,
    )
    FEEDBACK_STORE.append(action.incident_id, rec, alert=_alert_snapshot)

    return jsonify(
        {
            "ok": True,
            "incident_id": action.incident_id,
            "verdict": action.verdict,
            "feedback_id": rec.id,
            # Slack expects a 200 within 3s; the replacement message goes via
            # `response_url` if you want a richer reply (we keep this simple).
            "response_action": "clear",
        }
    )


# ---- Prompt A/B (L5) -----------------------------------------------------


@app.route("/api/prompts/variants", methods=["GET"])
def api_prompt_variants():
    """
    For every known agent: which variants exist on disk and which env-driven
    routing rules are active. Surfaces the A/B state to the dashboard so an
    SRE can see at a glance "we're running 10% on hypothesis-gen-conservative".
    """
    from sre_agent.personas import list_variants

    agents = [
        "log-detective",
        "metrics-analyst",
        "trace-reader",
        "deploy-historian",
        "hypothesis-gen",
        "remediation-sug",
    ]
    out = []
    for a in agents:
        env_a = a.upper().replace("-", "_")
        out.append(
            {
                "agent": a,
                "variants": list_variants(a),
                "pinned": os.environ.get(f"SRE_PROMPT_VARIANT_{env_a}") or None,
                "ab": os.environ.get(f"SRE_PROMPT_AB_{env_a}") or None,
            }
        )
    return jsonify({"agents": out})


# ---- auth / debug --------------------------------------------------------


@app.route("/api/auth/me", methods=["GET"])
def api_auth_me():
    """
    Surfaces auth state for the dashboard so the UI can decide whether
    to show "Sign in" prompts. Never returns secrets. When auth is off
    we return `enforced=False` and the caller can act freely.
    """
    from flask import g

    if not _auth_required_flag():
        return jsonify({"enforced": False})
    tok = getattr(g, "auth_token", None)
    if tok is None:
        token_str = request.headers.get("Authorization", "")
        from sre_agent.auth import REGISTRY, extract_bearer

        bearer = extract_bearer(token_str)
        if bearer:
            tok = REGISTRY.verify(bearer, required_scope="read")
    if tok is None:
        return jsonify({"enforced": True, "authenticated": False}), 401
    return jsonify(
        {
            "enforced": True,
            "authenticated": True,
            "token_name": tok.name,
            "scopes": list(tok.scopes),
        }
    )


# ---- health --------------------------------------------------------------


@app.route("/api/health", methods=["GET"])
def api_health():
    """Liveness — fast, no I/O. k8s `livenessProbe`."""
    return jsonify({"ok": True, "ts": _now_ms()})


@app.route("/api/readiness", methods=["GET"])
def api_readiness():
    """
    Deep readiness probe. Verifies every dependency the agent NEEDS to
    serve a real incident before declaring itself ready. k8s
    `readinessProbe` should hit this; if it returns 503 the pod gets
    pulled out of the service mesh until it recovers.
    """
    checks: dict[str, dict] = {}
    ok = True

    # 1. Graph compiled (cheap, but a fundamental check that the import
    #    chain isn't broken).
    try:
        _ = _GRAPH
        checks["graph"] = {"ok": True}
    except Exception as e:
        checks["graph"] = {"ok": False, "error": str(e)[:120]}
        ok = False

    # 2. Checkpointer reachable (LangGraph state store).
    try:
        state_dir = Path(os.environ.get("SRE_STATE_DIR") or "~/.sre-agent").expanduser()
        state_dir.mkdir(parents=True, exist_ok=True)
        checks["checkpointer"] = {
            "ok": True,
            "backend": os.environ.get("SRE_CHECKPOINTER", "sqlite"),
        }
    except Exception as e:
        checks["checkpointer"] = {"ok": False, "error": str(e)[:120]}
        ok = False

    # 3. Provider — for mock this is trivial; for real Datadog/Prom we'd
    #    do a tiny `GET /healthcheck` here. Defer to provider.health() if
    #    it exposes one.
    try:
        from sre_agent.providers import get_provider

        prov = get_provider()
        prov_check = {"ok": True, "name": prov.name}
        # Best-effort: providers may expose a non-blocking health hook.
        if hasattr(prov, "health"):
            prov_check.update(prov.health())  # type: ignore[attr-defined]
        checks["provider"] = prov_check
    except Exception as e:
        checks["provider"] = {"ok": False, "error": str(e)[:120]}
        ok = False

    # 4. Runbook store loaded.
    try:
        from sre_agent.runbooks.store import get_store

        store = get_store()
        # `size` is a @property on RunbookStore — accessed, not called.
        checks["runbooks"] = {"ok": True, "library_size": store.size}
    except Exception as e:
        # Runbooks are optional — failures here degrade but don't fail.
        checks["runbooks"] = {"ok": True, "degraded": True, "error": str(e)[:120]}

    body = {
        "ok": ok,
        "ts": _now_ms(),
        "checks": checks,
        "active_incidents": sum(
            1 for i in INCIDENTS.values() if i["phase"] == "investigating"
        ),
        "total_incidents": len(INCIDENTS),
    }
    return (jsonify(body), 200) if ok else (jsonify(body), 503)


@app.route("/api/health/legacy", methods=["GET"])
def api_health_legacy():
    """Old shape; kept so existing scripts don't break."""
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

def _maybe_seed_on_boot() -> None:
    """
    When `SRE_SEED_ON_BOOT=<N>` is set, generate <N> synthetic incidents
    into the dashboard's in-memory state at startup. Use only for demos
    and interview-prep environments — NEVER in real prod.

    Env knobs:
      * `SRE_SEED_ON_BOOT`     — number of incidents (required to fire)
      * `SRE_SEED_RNG_SEED`    — deterministic RNG seed (default 42)
      * `SRE_SEED_AB_FRACTION` — share of traffic routed to the variant
                                 prompt (default 0.1; bigger = stronger
                                 stat power)
      * `SRE_SEED_DAYS_BACK`   — spread incidents over this many days
                                 back (default 7)
    """
    raw = os.environ.get("SRE_SEED_ON_BOOT", "").strip()
    if not raw:
        return
    try:
        n = int(raw)
    except ValueError:
        print(f"SRE_SEED_ON_BOOT={raw!r} is not an integer; skipping seed.")
        return
    if n <= 0:
        return

    seed_value = int(os.environ.get("SRE_SEED_RNG_SEED", "42"))
    ab_fraction = float(os.environ.get("SRE_SEED_AB_FRACTION", "0.1"))
    days_back = int(os.environ.get("SRE_SEED_DAYS_BACK", "7"))

    try:
        from sre_agent.seed import seed as _seed_fn
    except Exception as e:
        print(f"could not import seeder: {e}")
        return

    print(
        f"seeding {n} synthetic incidents "
        f"(rng_seed={seed_value}, ab={ab_fraction}, days={days_back})..."
    )
    result = _seed_fn(
        n=n,
        seed_value=seed_value,
        days_back=days_back,
        ab_fraction=ab_fraction,
        incidents_dict=INCIDENTS,
    )
    print(
        f"  done: {result.n_incidents} incidents, {result.n_feedback} feedback, "
        f"{result.n_llm_records} llm records, {result.n_cache_hits} cache hits "
        f"in {result.duration_s:.1f}s"
    )


if __name__ == "__main__":
    # Bind to all interfaces so both `http://127.0.0.1:PORT` and `http://localhost:PORT`
    # work regardless of whether the OS resolves `localhost` to 127.0.0.1 or ::1.
    # (Some macOS setups + browsers prefer IPv6, and a 127.0.0.1-only bind fails.)
    host = os.environ.get("SRE_DASHBOARD_HOST", "0.0.0.0")
    _maybe_seed_on_boot()
    print(f"SRE Command Center on http://127.0.0.1:{PORT}  (also http://localhost:{PORT})")
    print(f"   {len(_MOCK_PROVIDER.list_scenarios())} demo scenarios loaded")
    app.run(host=host, port=PORT, debug=False, threaded=True)
