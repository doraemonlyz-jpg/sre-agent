"""
DatadogProvider — real Datadog API integration.

Maps our four evidence types onto Datadog's public APIs:

    fetch_logs    → POST /api/v2/logs/events/search
    fetch_metrics → GET  /api/v1/query   (x5 canonical metric queries)
    fetch_traces  → POST /api/v2/spans/events/search
    fetch_deploys → GET  /api/v1/events  (filtered to deploy markers)

Contract: NEVER raises. Every API failure becomes evidence with
`result=ERROR` so the LangGraph keeps running and the hypothesis generator
gets to weigh "no data" against the signals we did get.

The provider is HTTP-stack-agnostic — we use httpx, which `respx` can mock
at the transport layer. Tests therefore exercise the *real* parser code
against *real* Datadog response shapes; only the network is faked.

Env vars consumed:
    DD_API_KEY              required
    DD_APP_KEY              required
    DD_SITE                 default 'datadoghq.com'  (use 'datadoghq.eu',
                            'us3.datadoghq.com', etc. for non-US-east tenants)
    DD_HTTP_TIMEOUT_S       default '10'
"""

from __future__ import annotations

import contextlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, ClassVar

import httpx

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

logger = logging.getLogger("sre_agent.providers.datadog")


# The five canonical metric queries we ask Datadog for, in order. The
# `verdict` is computed downstream from baseline-vs-peak ratio; here we just
# fetch the raw series for the service in the supplied window.
_METRIC_TEMPLATES: list[tuple[str, str]] = [
    ("cpu_pct",       "avg:system.cpu.user{{service:{service}}}"),
    ("mem_pct",       "avg:system.mem.used{{service:{service}}}"),
    ("req_rate",      "sum:trace.flask.request.hits{{service:{service}}}.as_rate()"),
    ("error_rate",    "sum:trace.flask.request.errors{{service:{service}}}.as_rate()"),
    ("latency_p99",   "p99:trace.flask.request.duration{{service:{service}}}"),
]


def _unix_s(ts: datetime) -> int:
    """Datadog accepts unix seconds. Normalize naive timestamps to UTC."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return int(ts.timestamp())


def _verdict_from_series(baseline: float, peak: float) -> str:
    """Same heuristic the MockProvider uses — keep parity."""
    if baseline <= 0:
        return "SPIKE" if peak > 0 else "NORMAL"
    ratio = peak / max(baseline, 1e-9)
    if ratio >= 10:
        return f"SPIKE ({ratio:.0f}x)"
    if ratio >= 3:
        return f"ELEVATED ({ratio:.1f}x)"
    return "NORMAL"


class DatadogProvider(DataProvider):
    """Live Datadog provider. Reads creds from env at construction time."""

    name: ClassVar[str] = "datadog"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        app_key: str | None = None,
        site: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("DD_API_KEY")
        self.app_key = app_key or os.environ.get("DD_APP_KEY")
        self.site = site or os.environ.get("DD_SITE", "datadoghq.com")
        if not (self.api_key and self.app_key):
            raise RuntimeError(
                "DatadogProvider requires DD_API_KEY and DD_APP_KEY env vars "
                "(or explicit constructor args)."
            )
        self.base_url = f"https://api.{self.site}"
        timeout = float(os.environ.get("DD_HTTP_TIMEOUT_S", "10"))
        # Allow tests to inject a pre-built client so respx can hook in.
        self._client = client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "DD-API-KEY": self.api_key,
                "DD-APPLICATION-KEY": self.app_key,
                "Content-Type": "application/json",
            },
        )

    # ────────────────────────────────────────────────────────────────────
    # logs
    # ────────────────────────────────────────────────────────────────────

    def fetch_logs(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
        query: str = "status:error",
    ) -> LogsEvidence:
        body = {
            "filter": {
                "query": f"service:{service} {query}",
                "from": from_ts.isoformat(),
                "to":   to_ts.isoformat(),
            },
            "sort": "-timestamp",
            "page": {"limit": 100},
        }
        try:
            r = self._client.post("/api/v2/logs/events/search", json=body)
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            logger.warning("datadog.fetch_logs failed: %s", e)
            return LogsEvidence(
                result=EvidenceResult.ERROR,
                hits=0,
                interpretation=f"datadog logs API unreachable: {e}",
            )

        events = payload.get("data") or []
        if not events:
            return LogsEvidence(
                result=EvidenceResult.NO_SIGNAL,
                hits=0,
                interpretation=f"no error logs for {service} in window",
            )

        # Bucket by message → count, keep top 5.
        counter: dict[str, int] = {}
        timestamps: list[datetime] = []
        citations: list[str] = []
        for ev in events:
            attrs = ev.get("attributes", {}) or {}
            msg = (attrs.get("message") or "").strip()
            if msg:
                counter[msg] = counter.get(msg, 0) + 1
            ts = attrs.get("timestamp")
            if ts:
                with contextlib.suppress(ValueError):
                    timestamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
            if (lid := ev.get("id")):
                citations.append(f"log:{lid}")

        top = sorted(counter.items(), key=lambda kv: -kv[1])[:5]
        top_messages = [{"message": m, "count": c} for m, c in top]

        return LogsEvidence(
            result=EvidenceResult.FOUND,
            hits=len(events),
            first_at=min(timestamps) if timestamps else None,
            peak_at=max(timestamps) if timestamps else None,
            top_messages=top_messages,
            citations=citations[:10],
            interpretation=(
                f"{len(events)} error logs for {service}; "
                f"top message: {top_messages[0]['message'][:80]}"
                if top_messages else f"{len(events)} error logs (no messages)"
            ),
        )

    # ────────────────────────────────────────────────────────────────────
    # metrics
    # ────────────────────────────────────────────────────────────────────

    def fetch_metrics(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
    ) -> MetricsEvidence:
        from_s = _unix_s(from_ts)
        to_s = _unix_s(to_ts)
        snapshots: list[MetricSnapshot] = []
        errors: list[str] = []

        for label, tmpl in _METRIC_TEMPLATES:
            q = tmpl.format(service=service)
            try:
                r = self._client.get(
                    "/api/v1/query",
                    params={"from": from_s, "to": to_s, "query": q},
                )
                r.raise_for_status()
                snap = self._parse_metric_series(label, r.json())
                if snap:
                    snapshots.append(snap)
            except Exception as e:
                errors.append(f"{label}:{type(e).__name__}")
                logger.warning("datadog.fetch_metrics(%s) failed: %s", label, e)

        if not snapshots and errors:
            return MetricsEvidence(
                result=EvidenceResult.ERROR,
                interpretation=f"all metric queries failed: {','.join(errors)}",
            )

        spike_count = sum(1 for s in snapshots if s.is_spike)
        if not snapshots:
            return MetricsEvidence(
                result=EvidenceResult.NO_SIGNAL,
                interpretation=f"no metric points for {service} in window",
            )

        # Crude same-minute correlation — if 2+ metrics peak within 60s of each
        # other, flag it. The hypothesis generator uses this.
        correlation = None
        spikes_with_peak = [(s.name, s.peak_at) for s in snapshots if s.is_spike and s.peak_at]
        if len(spikes_with_peak) >= 2:
            spikes_with_peak.sort(key=lambda x: x[1])
            for i in range(len(spikes_with_peak) - 1):
                dt = (spikes_with_peak[i + 1][1] - spikes_with_peak[i][1]).total_seconds()
                if abs(dt) < 60:
                    correlation = (
                        f"{spikes_with_peak[i][0]} and {spikes_with_peak[i+1][0]} "
                        f"peaked within {abs(dt):.0f}s of each other"
                    )
                    break

        return MetricsEvidence(
            result=EvidenceResult.FOUND if spike_count else EvidenceResult.NO_SIGNAL,
            metrics=snapshots,
            correlation=correlation,
            interpretation=(
                f"{spike_count}/{len(snapshots)} metrics spiking for {service}"
                if spike_count else f"all {len(snapshots)} metrics nominal"
            ),
        )

    @staticmethod
    def _parse_metric_series(label: str, payload: dict[str, Any]) -> MetricSnapshot | None:
        series = payload.get("series") or []
        if not series:
            return None
        # Datadog returns one series per scope; take the first.
        points = series[0].get("pointlist") or []
        if not points:
            return None

        # pointlist format: [[unix_ms, value], ...]
        values = [(int(p[0]), float(p[1])) for p in points if len(p) >= 2 and p[1] is not None]
        if not values:
            return None

        # Baseline = median of first 20% of window; peak = max in window.
        head = max(1, len(values) // 5)
        baseline_vals = sorted(v for _, v in values[:head])
        baseline = baseline_vals[len(baseline_vals) // 2]
        peak_ts, peak = max(values, key=lambda kv: kv[1])
        peak_at = datetime.fromtimestamp(peak_ts / 1000, tz=timezone.utc)

        return MetricSnapshot(
            name=label,
            baseline=round(baseline, 3),
            peak=round(peak, 3),
            peak_at=peak_at,
            verdict=_verdict_from_series(baseline, peak),
        )

    # ────────────────────────────────────────────────────────────────────
    # traces
    # ────────────────────────────────────────────────────────────────────

    def fetch_traces(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
        only_errored: bool = True,
    ) -> TracesEvidence:
        q = f"service:{service}"
        if only_errored:
            q += " status:error"
        body = {
            "filter": {
                "query": q,
                "from": from_ts.isoformat(),
                "to":   to_ts.isoformat(),
            },
            "sort": "-@duration",
            "page": {"limit": 50},
        }
        try:
            r = self._client.post("/api/v2/spans/events/search", json=body)
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            logger.warning("datadog.fetch_traces failed: %s", e)
            return TracesEvidence(
                result=EvidenceResult.ERROR,
                traces_inspected=0,
                error_rate="0/0",
                interpretation=f"datadog APM API unreachable: {e}",
            )

        spans = payload.get("data") or []
        if not spans:
            return TracesEvidence(
                result=EvidenceResult.NO_SIGNAL,
                traces_inspected=0,
                error_rate="0/0",
                interpretation=f"no spans for {service} in window",
            )

        # Group by operation name.
        by_name: dict[str, list[float]] = {}
        downstream_services: set[str] = set()
        errored = 0
        for sp in spans:
            attrs = sp.get("attributes", {}) or {}
            name = attrs.get("name") or attrs.get("resource_name") or "unknown"
            dur_ns = attrs.get("duration")
            if dur_ns is None:
                continue
            by_name.setdefault(name, []).append(float(dur_ns) / 1e6)  # → ms
            if (attrs.get("status") or "").lower() == "error":
                errored += 1
            sv = attrs.get("service")
            if sv and sv != service:
                downstream_services.add(sv)

        # Hot span = the operation with the biggest baseline→median jump.
        hot: HotSpan | None = None
        if by_name:
            candidate = None
            best_ratio = 0.0
            for name, durs in by_name.items():
                if len(durs) < 2:
                    continue
                durs_sorted = sorted(durs)
                baseline = durs_sorted[len(durs_sorted) // 4]  # p25 as baseline
                median = durs_sorted[len(durs_sorted) // 2]
                if baseline > 0 and (median / baseline) > best_ratio:
                    best_ratio = median / baseline
                    candidate = (name, baseline, median)
            if candidate:
                name, baseline, median = candidate
                hot = HotSpan(
                    service=service,
                    name=name,
                    baseline_ms=round(baseline, 1),
                    median_ms=round(median, 1),
                    ratio=f"{best_ratio:.1f}x",
                )

        return TracesEvidence(
            result=EvidenceResult.FOUND if errored or hot else EvidenceResult.NO_SIGNAL,
            traces_inspected=len(spans),
            error_rate=f"{errored}/{len(spans)}",
            hot_span=hot,
            downstream_suspect=(
                f"errors correlate with downstream call to {sorted(downstream_services)[0]}"
                if downstream_services and errored else None
            ),
            interpretation=(
                f"hot span: {hot.name} ({hot.ratio})"
                if hot else f"{errored}/{len(spans)} traces errored"
            ),
        )

    # ────────────────────────────────────────────────────────────────────
    # deploys
    # ────────────────────────────────────────────────────────────────────

    def fetch_deploys(
        self,
        *,
        services: list[str],
        from_ts: datetime,
        to_ts: datetime,
    ) -> DeploysEvidence:
        # Datadog convention: deploys are emitted as Events tagged source:deploy
        # (or whatever your CI tags with). We accept either source:deploy or
        # tag:deploy.
        tag_filter = ",".join(f"service:{s}" for s in services) if services else ""
        try:
            r = self._client.get(
                "/api/v1/events",
                params={
                    "start": _unix_s(from_ts),
                    "end":   _unix_s(to_ts),
                    "sources": "deploy",
                    "tags": tag_filter,
                },
            )
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            logger.warning("datadog.fetch_deploys failed: %s", e)
            return DeploysEvidence(
                result=EvidenceResult.ERROR,
                interpretation=f"datadog events API unreachable: {e}",
            )

        events = payload.get("events") or []
        deploys: list[DeployRecord] = []
        for ev in events:
            tags = {t.split(":", 1)[0]: t.split(":", 1)[1]
                    for t in (ev.get("tags") or []) if ":" in t}
            svc = tags.get("service") or (services[0] if services else "unknown")
            sha = tags.get("sha") or tags.get("revision") or ""
            pr_url = ev.get("url") or tags.get("pr_url") or ""
            ts = datetime.fromtimestamp(ev.get("date_happened", 0), tz=timezone.utc)
            minutes_before = max(0.0, (to_ts.replace(tzinfo=timezone.utc) - ts).total_seconds() / 60)
            # Crude suspect score — closer to the alert = more suspect.
            if minutes_before <= 30:
                suspect = "HIGH"
            elif minutes_before <= 120:
                suspect = "MEDIUM"
            else:
                suspect = "LOW"
            deploys.append(
                DeployRecord(
                    service=svc,
                    sha=sha,
                    pr_url=pr_url,
                    pr_title=ev.get("title") or "(no title)",
                    author=tags.get("author") or "unknown",
                    deployed_at=ts,
                    minutes_before=round(minutes_before, 1),
                    suspect=suspect,  # type: ignore[arg-type]
                )
            )

        return DeploysEvidence(
            result=EvidenceResult.FOUND if deploys else EvidenceResult.NO_SIGNAL,
            deploys=deploys,
            interpretation=(
                f"{len(deploys)} deploys in window"
                if deploys else "no deploys in window — likely not a code regression"
            ),
        )

    # ────────────────────────────────────────────────────────────────────
    # housekeeping
    # ────────────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> DatadogProvider:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
