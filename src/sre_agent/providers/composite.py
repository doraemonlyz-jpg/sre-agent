"""
CompositeProvider — fan out each evidence type to a different real backend.

Different observability platforms specialize: Prometheus does metrics,
Loki does logs, Tempo/Jaeger does traces, your CI emits deploy events.
A single Datadog or New Relic can do all four, but the open-source world
is composed of specialists.

`CompositeProvider` lets you wire each `fetch_*` method to a *different*
provider. Anything left unset returns NO_SIGNAL evidence with an
explanatory `interpretation` — the LangGraph still runs deterministically.

Typical usage:

    provider = CompositeProvider(
        logs=LokiProvider(),
        metrics=PrometheusProvider(),
        # traces/deploys unset → NO_SIGNAL evidence
    )

This is also how `get_provider("oss")` builds a Prometheus+Loki stack.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from sre_agent.providers.base import DataProvider
from sre_agent.schemas import (
    DeploysEvidence,
    EvidenceResult,
    LogsEvidence,
    MetricsEvidence,
    TracesEvidence,
)


class CompositeProvider(DataProvider):
    """Routes each `fetch_*` to the provider configured for that evidence type."""

    name: ClassVar[str] = "composite"

    def __init__(
        self,
        *,
        logs:    DataProvider | None = None,
        metrics: DataProvider | None = None,
        traces:  DataProvider | None = None,
        deploys: DataProvider | None = None,
    ) -> None:
        self.logs_p    = logs
        self.metrics_p = metrics
        self.traces_p  = traces
        self.deploys_p = deploys

    # ──────────────────────────────────────────────────────────────────

    def fetch_logs(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
        query: str = "status:error",
    ) -> LogsEvidence:
        if self.logs_p is None:
            return LogsEvidence(
                result=EvidenceResult.NO_SIGNAL,
                hits=0,
                interpretation="no logs provider configured (set composite.logs)",
            )
        return self.logs_p.fetch_logs(
            service=service, from_ts=from_ts, to_ts=to_ts, query=query
        )

    def fetch_metrics(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
    ) -> MetricsEvidence:
        if self.metrics_p is None:
            return MetricsEvidence(
                result=EvidenceResult.NO_SIGNAL,
                interpretation="no metrics provider configured (set composite.metrics)",
            )
        return self.metrics_p.fetch_metrics(
            service=service, from_ts=from_ts, to_ts=to_ts
        )

    def fetch_traces(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
        only_errored: bool = True,
    ) -> TracesEvidence:
        if self.traces_p is None:
            return TracesEvidence(
                result=EvidenceResult.NO_SIGNAL,
                traces_inspected=0,
                error_rate="0/0",
                interpretation="no traces provider configured (set composite.traces)",
            )
        return self.traces_p.fetch_traces(
            service=service, from_ts=from_ts, to_ts=to_ts, only_errored=only_errored
        )

    def fetch_deploys(
        self,
        *,
        services: list[str],
        from_ts: datetime,
        to_ts: datetime,
    ) -> DeploysEvidence:
        if self.deploys_p is None:
            return DeploysEvidence(
                result=EvidenceResult.NO_SIGNAL,
                interpretation="no deploys provider configured (set composite.deploys)",
            )
        return self.deploys_p.fetch_deploys(
            services=services, from_ts=from_ts, to_ts=to_ts
        )

    # ──────────────────────────────────────────────────────────────────

    def close(self) -> None:
        for p in (self.logs_p, self.metrics_p, self.traces_p, self.deploys_p):
            close = getattr(p, "close", None)
            if callable(close):
                close()
