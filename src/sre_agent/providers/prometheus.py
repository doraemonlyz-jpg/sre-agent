"""
PrometheusProvider — metrics-only data source for the open-source stack.

Maps `fetch_metrics` onto Prometheus's `/api/v1/query_range`. The other three
methods (logs/traces/deploys) return NO_SIGNAL — Prometheus doesn't store
those signal types. Combine with a LokiProvider via `CompositeProvider` to
get a full open-source replacement for Datadog.

Why we still implement `fetch_logs/traces/deploys` here at all: the
`DataProvider` ABC requires them. We satisfy the interface with cheap
NO_SIGNAL evidence so the LangGraph still runs deterministically when a
caller hands a bare PrometheusProvider to a node that asks for logs.

Env vars consumed:
    PROMETHEUS_URL          default 'http://localhost:9090'
    PROMETHEUS_HTTP_TIMEOUT_S default '10'

Query overrides — set any of these to point at your own metric names:
    PROM_QUERY_REQ_RATE
    PROM_QUERY_ERROR_RATE
    PROM_QUERY_LATENCY_P99
    PROM_QUERY_CPU
    PROM_QUERY_MEM
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, ClassVar

import httpx

from sre_agent.providers._http import (
    RetryingClient,
    make_retrying_client,
    probe_health,
)
from sre_agent.providers.base import DataProvider
from sre_agent.schemas import (
    DeploysEvidence,
    EvidenceResult,
    LogsEvidence,
    MetricsEvidence,
    MetricSnapshot,
    TracesEvidence,
)

logger = logging.getLogger("sre_agent.providers.prometheus")


# Default PromQL templates. {service} is substituted at fetch time.
# These match the chaos-app exporter in demo-stack/.
_DEFAULT_QUERIES: dict[str, str] = {
    "req_rate":     'sum(rate(chaos_requests_total{{service="{service}"}}[1m]))',
    "error_rate":   'sum(rate(chaos_errors_total{{service="{service}"}}[1m]))',
    "latency_p99":  'histogram_quantile(0.99, sum by (le) (rate(chaos_latency_seconds_bucket{{service="{service}"}}[1m])))',
    "cpu_pct":      'avg(process_cpu_seconds_total{{service="{service}"}})',
    "mem_pct":      'avg(process_resident_memory_bytes{{service="{service}"}}) / 1024 / 1024',
}

_ENV_OVERRIDE_KEYS: dict[str, str] = {
    "req_rate":    "PROM_QUERY_REQ_RATE",
    "error_rate":  "PROM_QUERY_ERROR_RATE",
    "latency_p99": "PROM_QUERY_LATENCY_P99",
    "cpu_pct":     "PROM_QUERY_CPU",
    "mem_pct":     "PROM_QUERY_MEM",
}


def _verdict(baseline: float, peak: float) -> str:
    """Same rule used by MockProvider + DatadogProvider — keep parity."""
    if baseline <= 0:
        return "SPIKE" if peak > 0 else "NORMAL"
    ratio = peak / max(baseline, 1e-9)
    if ratio >= 10:
        return f"SPIKE ({ratio:.0f}x)"
    if ratio >= 3:
        return f"ELEVATED ({ratio:.1f}x)"
    return "NORMAL"


def _unix_s(ts: datetime) -> float:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.timestamp()


class PrometheusProvider(DataProvider):
    """Live Prometheus provider. Implements `fetch_metrics`; rest return NO_SIGNAL."""

    name: ClassVar[str] = "prometheus"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        queries: dict[str, str] | None = None,
        client: httpx.Client | RetryingClient | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("PROMETHEUS_URL", "http://localhost:9090")).rstrip("/")
        timeout = float(os.environ.get("PROMETHEUS_HTTP_TIMEOUT_S", "10"))
        # Allow per-query overrides through env vars so users can plug this
        # into any metric-naming convention.
        self.queries: dict[str, str] = {}
        merged = {**_DEFAULT_QUERIES, **(queries or {})}
        for label, tmpl in merged.items():
            env_key = _ENV_OVERRIDE_KEYS.get(label)
            if env_key and os.environ.get(env_key):
                self.queries[label] = os.environ[env_key]
            else:
                self.queries[label] = tmpl
        # Default client: retrying + auth-aware. Tests inject their own
        # via `client=`.
        if client is not None:
            self._client = client
        else:
            self._client = make_retrying_client(
                base_url=self.base_url,
                timeout_s=timeout,
                provider_name="prometheus",
                auth_env_prefix="PROMETHEUS",
            )

    # ── fetch_metrics ─────────────────────────────────────────────────

    def fetch_metrics(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
    ) -> MetricsEvidence:
        # Pick a step so the time range gives us ~60 points (Prometheus caps
        # query_range at 11k points; 60 is plenty for baseline/peak detection).
        window_s = max(60.0, _unix_s(to_ts) - _unix_s(from_ts))
        step_s = max(1, int(window_s / 60))

        snapshots: list[MetricSnapshot] = []
        errors: list[str] = []

        for label, tmpl in self.queries.items():
            query = tmpl.format(service=service)
            try:
                r = self._client.get(
                    "/api/v1/query_range",
                    params={
                        "query": query,
                        "start": _unix_s(from_ts),
                        "end":   _unix_s(to_ts),
                        "step":  step_s,
                    },
                )
                r.raise_for_status()
                snap = self._parse_query_range(label, r.json())
                if snap:
                    snapshots.append(snap)
            except Exception as e:
                errors.append(f"{label}:{type(e).__name__}")
                logger.warning("prometheus.fetch_metrics(%s) failed: %s", label, e)

        if not snapshots and errors:
            return MetricsEvidence(
                result=EvidenceResult.ERROR,
                interpretation=f"prometheus query_range failed: {','.join(errors)}",
            )
        if not snapshots:
            return MetricsEvidence(
                result=EvidenceResult.NO_SIGNAL,
                interpretation=f"no metric points returned for {service} in window",
            )

        spike_count = sum(1 for s in snapshots if s.is_spike)

        # Same-minute correlation across spiking metrics.
        correlation: str | None = None
        peaks = [(s.name, s.peak_at) for s in snapshots if s.is_spike and s.peak_at]
        if len(peaks) >= 2:
            peaks.sort(key=lambda x: x[1])
            for i in range(len(peaks) - 1):
                dt = (peaks[i + 1][1] - peaks[i][1]).total_seconds()
                if abs(dt) < 60:
                    correlation = (
                        f"{peaks[i][0]} and {peaks[i + 1][0]} "
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
    def _parse_query_range(label: str, payload: dict[str, Any]) -> MetricSnapshot | None:
        """
        Prometheus query_range returns:

            {"status": "success",
             "data": {"resultType": "matrix",
                      "result": [{"metric": {...},
                                  "values": [[1715000000, "0.05"], ...]}]}}
        """
        if payload.get("status") != "success":
            return None
        result = (payload.get("data") or {}).get("result") or []
        if not result:
            return None
        values = result[0].get("values") or []
        # `(ts: float, val: str)` — Prometheus encodes values as strings to
        # preserve precision; skip "NaN" sentinels.
        parsed: list[tuple[float, float]] = []
        for v in values:
            if len(v) < 2:
                continue
            try:
                val = float(v[1])
            except (ValueError, TypeError):
                continue
            if val != val:  # NaN
                continue
            parsed.append((float(v[0]), val))
        if not parsed:
            return None

        head = max(1, len(parsed) // 5)
        baseline_vals = sorted(p[1] for p in parsed[:head])
        baseline = baseline_vals[len(baseline_vals) // 2]
        peak_ts, peak = max(parsed, key=lambda kv: kv[1])
        peak_at = datetime.fromtimestamp(peak_ts, tz=timezone.utc)

        return MetricSnapshot(
            name=label,
            baseline=round(baseline, 3),
            peak=round(peak, 3),
            peak_at=peak_at,
            verdict=_verdict(baseline, peak),
        )

    # ── unsupported pillars: return NO_SIGNAL ────────────────────────

    def fetch_logs(self, **_kwargs: Any) -> LogsEvidence:
        return LogsEvidence(
            result=EvidenceResult.NO_SIGNAL,
            hits=0,
            interpretation="PrometheusProvider does not handle logs (use LokiProvider)",
        )

    def fetch_traces(self, **_kwargs: Any) -> TracesEvidence:
        return TracesEvidence(
            result=EvidenceResult.NO_SIGNAL,
            traces_inspected=0,
            error_rate="0/0",
            interpretation="PrometheusProvider does not handle traces (use Tempo/Jaeger)",
        )

    def fetch_deploys(self, **_kwargs: Any) -> DeploysEvidence:
        return DeploysEvidence(
            result=EvidenceResult.NO_SIGNAL,
            interpretation="PrometheusProvider does not track deploys (use GitHub/CI events)",
        )

    # ── health ────────────────────────────────────────────────────────
    #
    # Surfaced via the dashboard's /api/readiness probe. We hit
    # `/-/healthy`, the canonical Prometheus liveness endpoint -- it's
    # cheap, doesn't run a query, and unambiguously signals "the
    # Prometheus process is up".
    def health(self) -> dict[str, Any]:
        return probe_health(self._client, path="/-/healthy")

    # ── housekeeping ──────────────────────────────────────────────────

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PrometheusProvider:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
