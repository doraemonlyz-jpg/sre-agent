"""
MockProvider — reads from `mocks/scenarios.json` instead of hitting Datadog.

Used for:
- Local dev (no Datadog token needed)
- Tests (deterministic, no network)
- The dashboard demo button

Real production picks scenarios by `service`. For tests / CLI we also support
pinning to a specific `scenario_id` to force a particular outcome.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from sre_agent.providers.base import DataProvider
from sre_agent.schemas import (
    DeployRecord,
    DeploysEvidence,
    EvidenceResult,
    HotSpan,
    LogsEvidence,
    MetricsEvidence,
    MetricSnapshot,
    TracesEvidence,
)


def _default_scenarios_path() -> Path:
    """Find mocks/scenarios.json. Repo layout or env override."""
    env = os.environ.get("SRE_MOCK_PATH")
    if env:
        return Path(env)
    # Repo layout: sre-agent/mocks/scenarios.json
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "mocks" / "scenarios.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("mocks/scenarios.json not found; set SRE_MOCK_PATH.")


class MockProvider(DataProvider):
    """In-memory provider backed by scenarios.json."""

    name: ClassVar[str] = "mock"

    def __init__(self, scenarios_path: Path | None = None) -> None:
        path = scenarios_path or _default_scenarios_path()
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        self._scenarios: dict[str, dict[str, Any]] = {
            s["id"]: s for s in data["scenarios"]
        }

    # ── lookup helpers ────────────────────────────────────────────────

    def _scenario_for(
        self,
        *,
        service: str,
        scenario_id_hint: str | None = None,
    ) -> dict[str, Any] | None:
        # Explicit pin wins.
        if scenario_id_hint and scenario_id_hint in self._scenarios:
            return self._scenarios[scenario_id_hint]
        # Fall back to service-name match.
        for s in self._scenarios.values():
            if s["alert"]["service"] == service:
                return s
        return None

    def get_scenario_alert(self, scenario_id: str) -> dict[str, Any]:
        """Helper for the dashboard / CLI to seed an alert from a scenario."""
        return self._scenarios[scenario_id]["alert"]

    def list_scenarios(self) -> list[dict[str, str]]:
        return [
            {"id": s["id"], "label": s["label"], "service": s["alert"]["service"]}
            for s in self._scenarios.values()
        ]

    # ── DataProvider interface ────────────────────────────────────────

    def fetch_logs(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
        query: str = "status:error",
        scenario_id: str | None = None,
    ) -> LogsEvidence:
        scen = self._scenario_for(service=service, scenario_id_hint=scenario_id)
        if not scen:
            return LogsEvidence(
                result=EvidenceResult.NO_SIGNAL,
                hits=0,
                interpretation=f"No mock data for service '{service}'.",
            )
        logs = scen["logs"]
        return LogsEvidence(
            result=EvidenceResult.NO_SIGNAL if logs["hits"] <= 5 else EvidenceResult.FOUND,
            hits=logs["hits"],
            first_at=logs.get("first_at"),
            peak_at=logs.get("peak_at"),
            top_messages=logs.get("top_messages", []),
            citations=[
                f"log_id:{s['log_id']} at {s['timestamp']}"
                for s in logs.get("samples", [])[:3]
            ],
            interpretation=_log_interpretation(logs),
        )

    def fetch_metrics(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
        scenario_id: str | None = None,
    ) -> MetricsEvidence:
        scen = self._scenario_for(service=service, scenario_id_hint=scenario_id)
        if not scen:
            return MetricsEvidence(
                result=EvidenceResult.NO_SIGNAL,
                interpretation=f"No mock metrics for service '{service}'.",
            )
        m = scen["metrics"]
        snapshots = [
            MetricSnapshot(
                name=name,
                baseline=v["baseline"],
                peak=v["peak"],
                peak_at=v.get("peak_at"),
                verdict=v["verdict"],
            )
            for name, v in m.items()
        ]
        spike_names = [s.name for s in snapshots if s.is_spike]
        correlation = None
        if len(spike_names) >= 2:
            correlation = f"{', '.join(spike_names)} all spike together — same root cause."
        return MetricsEvidence(
            result=EvidenceResult.FOUND if spike_names else EvidenceResult.NO_SIGNAL,
            metrics=snapshots,
            correlation=correlation,
            interpretation=(
                "All metrics in baseline — no capacity issue here."
                if not spike_names
                else f"Anomaly on {', '.join(spike_names)} — points to a "
                + ("traffic problem" if "request_rate" in spike_names else "downstream / dependency issue")
                + "."
            ),
        )

    def fetch_traces(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
        only_errored: bool = True,
        scenario_id: str | None = None,
    ) -> TracesEvidence:
        scen = self._scenario_for(service=service, scenario_id_hint=scenario_id)
        if not scen:
            return TracesEvidence(
                result=EvidenceResult.NO_SIGNAL,
                traces_inspected=0,
                error_rate="0/0",
                interpretation=f"No APM data for service '{service}'.",
            )
        t = scen["traces"]
        hot_span = None
        if t.get("hot_span"):
            hs = t["hot_span"]
            hot_span = HotSpan(
                service=hs["service"],
                name=hs["name"],
                baseline_ms=hs["baseline_ms"],
                median_ms=hs["median_ms"],
                ratio=hs["ratio"],
            )
        return TracesEvidence(
            result=EvidenceResult.FOUND if hot_span else EvidenceResult.NO_SIGNAL,
            traces_inspected=t["traces_inspected"],
            error_rate=t["error_rate"],
            hot_span=hot_span,
            downstream_suspect=t.get("downstream_suspect"),
            citations=[
                f"trace_id:{s['trace_id']} ({s['duration_ms']}ms)"
                for s in t.get("sample_trace_ids", [])[:3]
            ],
            interpretation=(
                f"{t['error_rate']} traces errored with hot span "
                f"`{hot_span.name}` at {hot_span.ratio} baseline — {t.get('downstream_suspect') or 'no downstream'}."
                if hot_span
                else "No anomalous traces in window."
            ),
        )

    def fetch_deploys(
        self,
        *,
        services: list[str],
        from_ts: datetime,
        to_ts: datetime,
        scenario_id: str | None = None,
    ) -> DeploysEvidence:
        scen = None
        if scenario_id and scenario_id in self._scenarios:
            scen = self._scenarios[scenario_id]
        else:
            for svc in services:
                cand = self._scenario_for(service=svc)
                if cand:
                    scen = cand
                    break
        if not scen:
            return DeploysEvidence(
                result=EvidenceResult.NO_SIGNAL,
                interpretation="No deploys found for any candidate service.",
            )
        d = scen["deploys"]
        records = [
            DeployRecord(**dep) for dep in d.get("deploys", [])
        ]
        result = EvidenceResult.FOUND if records else EvidenceResult.NO_SIGNAL
        return DeploysEvidence(
            result=result,
            deploys=records,
            config_changes=d.get("config_changes", []),
            citations=[r.pr_url for r in records],
            interpretation=(
                "No deploys in 2h window — likely not a code regression."
                if not records
                else (
                    f"{records[0].service} deployed {records[0].minutes_before:.0f}min before — "
                    f"suspect {records[0].suspect}."
                )
            ),
        )


def _log_interpretation(logs: dict[str, Any]) -> str:
    """Cheap rule-based interpretation (mock doesn't need an LLM for this)."""
    if logs["hits"] <= 5:
        return f"{logs['hits']} hits is baseline noise; no signal."
    tops = logs.get("top_messages") or []
    if not tops:
        return f"{logs['hits']} errors but no dominant message — likely cascading."
    top = tops[0]
    pct = round(100 * top["count"] / logs["hits"])
    return (
        f"{logs['hits']} errors; {pct}% are: \"{top['message'][:80]}\". "
        f"Dominant message → likely a single root cause."
    )
