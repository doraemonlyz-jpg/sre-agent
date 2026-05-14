"""
LokiProvider — logs-only data source for the open-source stack.

Calls Grafana Loki's `/loki/api/v1/query_range` endpoint. Logs are queried
with LogQL — by default we use `{service="$service"} |~ "(?i)error|exception"`
which catches the common error patterns the demo chaos-app emits.

Combine with `PrometheusProvider` via `CompositeProvider` to cover both
logs and metrics with a fully open-source observability stack.

Env vars:
    LOKI_URL                default 'http://localhost:3100'
    LOKI_QUERY              LogQL template (default catches errors/exceptions)
    LOKI_HTTP_TIMEOUT_S     default '10'
"""

from __future__ import annotations

import contextlib
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
    TracesEvidence,
)

logger = logging.getLogger("sre_agent.providers.loki")


# LogQL default — catches the chaos-app's structured error emissions and
# generic uncaught exceptions. Override via `LOKI_QUERY` env var.
_DEFAULT_QUERY = '{{service="{service}"}} |~ "(?i)error|exception|panic"'


def _unix_ns(ts: datetime) -> int:
    """Loki accepts unix nanoseconds as integers or strings."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return int(ts.timestamp() * 1_000_000_000)


class LokiProvider(DataProvider):
    """Live Grafana Loki provider. Implements `fetch_logs`; rest return NO_SIGNAL."""

    name: ClassVar[str] = "loki"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        query_template: str | None = None,
        client: httpx.Client | RetryingClient | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("LOKI_URL", "http://localhost:3100")).rstrip("/")
        self.query_template = (
            query_template
            or os.environ.get("LOKI_QUERY")
            or _DEFAULT_QUERY
        )
        timeout = float(os.environ.get("LOKI_HTTP_TIMEOUT_S", "10"))
        if client is not None:
            self._client = client
        else:
            self._client = make_retrying_client(
                base_url=self.base_url,
                timeout_s=timeout,
                provider_name="loki",
                auth_env_prefix="LOKI",
            )

    # ── fetch_logs ────────────────────────────────────────────────────

    def fetch_logs(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
        query: str | None = None,
    ) -> LogsEvidence:
        logql = (query or self.query_template).format(service=service)
        try:
            r = self._client.get(
                "/loki/api/v1/query_range",
                params={
                    "query": logql,
                    "start": _unix_ns(from_ts),
                    "end":   _unix_ns(to_ts),
                    "limit": 500,
                    "direction": "backward",
                },
            )
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            logger.warning("loki.fetch_logs failed: %s", e)
            return LogsEvidence(
                result=EvidenceResult.ERROR,
                hits=0,
                interpretation=f"loki query_range unreachable: {e}",
            )

        if (payload.get("status") or "") != "success":
            return LogsEvidence(
                result=EvidenceResult.ERROR,
                hits=0,
                interpretation=f"loki returned non-success status: {payload.get('status')!r}",
            )

        streams = (payload.get("data") or {}).get("result") or []
        if not streams:
            return LogsEvidence(
                result=EvidenceResult.NO_SIGNAL,
                hits=0,
                interpretation=f"no matching logs for {service} in window",
            )

        # Flatten all stream values: each value is `[ns_string, line]`.
        counter: dict[str, int] = {}
        timestamps: list[datetime] = []
        total = 0
        citations: list[str] = []
        for stream in streams:
            values = stream.get("values") or []
            stream_labels = stream.get("stream") or {}
            for v in values:
                if len(v) < 2:
                    continue
                ns, line = v[0], v[1]
                total += 1
                msg = (line or "").strip()
                if msg:
                    # Bucket by the first 120 chars to avoid pathological cardinality.
                    key = msg[:120]
                    counter[key] = counter.get(key, 0) + 1
                with contextlib.suppress(ValueError, TypeError):
                    timestamps.append(
                        datetime.fromtimestamp(int(ns) / 1_000_000_000, tz=timezone.utc)
                    )
            # One citation per stream is enough for the PM to re-run the query.
            if stream_labels and len(citations) < 5:
                lbl = ",".join(f"{k}={v}" for k, v in stream_labels.items())
                citations.append(f"loki:{{{lbl}}}")

        top = sorted(counter.items(), key=lambda kv: -kv[1])[:5]
        top_messages = [{"message": m, "count": c} for m, c in top]

        return LogsEvidence(
            result=EvidenceResult.FOUND,
            hits=total,
            first_at=min(timestamps) if timestamps else None,
            peak_at=max(timestamps) if timestamps else None,
            top_messages=top_messages,
            citations=citations,
            interpretation=(
                f"{total} matching logs for {service}; "
                f"top: {top_messages[0]['message'][:80]}"
                if top_messages else f"{total} matching logs (no message text)"
            ),
        )

    # ── unsupported pillars: return NO_SIGNAL ────────────────────────

    def fetch_metrics(self, **_kwargs: Any) -> MetricsEvidence:
        return MetricsEvidence(
            result=EvidenceResult.NO_SIGNAL,
            interpretation="LokiProvider does not handle metrics (use PrometheusProvider)",
        )

    def fetch_traces(self, **_kwargs: Any) -> TracesEvidence:
        return TracesEvidence(
            result=EvidenceResult.NO_SIGNAL,
            traces_inspected=0,
            error_rate="0/0",
            interpretation="LokiProvider does not handle traces (use Tempo/Jaeger)",
        )

    def fetch_deploys(self, **_kwargs: Any) -> DeploysEvidence:
        return DeploysEvidence(
            result=EvidenceResult.NO_SIGNAL,
            interpretation="LokiProvider does not track deploys (use GitHub/CI events)",
        )

    # ── health ────────────────────────────────────────────────────────
    #
    # Loki exposes `/ready` (k8s-style readiness) and `/metrics`. We hit
    # `/ready` because it's the cheapest and matches the Helm chart's
    # default probe. Returning 200 means the in-memory chunk indexer is
    # ready -- which is exactly what we need before issuing query_range.
    def health(self) -> dict[str, Any]:
        return probe_health(self._client, path="/ready")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> LokiProvider:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
