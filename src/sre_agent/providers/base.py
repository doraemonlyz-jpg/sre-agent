"""
DataProvider abstract base — every concrete provider (mock, Datadog, etc.)
implements these 4 methods. The graph nodes only ever call this interface;
they never see Datadog API specifics.

Each method returns a typed Pydantic evidence object. If the upstream API
fails, the provider returns an evidence object with result=ERROR — never
raises. The graph treats partial evidence as a normal outcome.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from sre_agent.schemas import (
    DeploysEvidence,
    LogsEvidence,
    MetricsEvidence,
    TracesEvidence,
)


class DataProvider(ABC):
    """
    Abstract data source. Implementations: MockProvider, DatadogProvider, ...

    Methods are deliberately narrow — one method per evidence type. Each
    returns a strict Pydantic object.
    """

    name: str  # e.g. "mock", "datadog"

    @abstractmethod
    def fetch_logs(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
        query: str = "status:error",
    ) -> LogsEvidence:
        """Fetch error logs in window. NEVER raises; uses result=ERROR on failure."""

    @abstractmethod
    def fetch_metrics(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
    ) -> MetricsEvidence:
        """Fetch the canonical 5 metrics (cpu/mem/req-rate/error-rate/latency-p99)."""

    @abstractmethod
    def fetch_traces(
        self,
        *,
        service: str,
        from_ts: datetime,
        to_ts: datetime,
        only_errored: bool = True,
    ) -> TracesEvidence:
        """Pull recent APM traces and identify the hot span."""

    @abstractmethod
    def fetch_deploys(
        self,
        *,
        services: list[str],
        from_ts: datetime,
        to_ts: datetime,
    ) -> DeploysEvidence:
        """Look up deploys/config changes for the service and immediate neighbours."""
