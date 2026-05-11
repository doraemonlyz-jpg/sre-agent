"""
DatadogProvider — real Datadog API integration (stub for v1).

Set SRE_DATA_PROVIDER=datadog and provide DD_API_KEY + DD_APP_KEY.

Implementation outline:
- logs:   POST /api/v2/logs/events/search
- metrics:GET  /api/v1/query?query=...&from=..&to=..
- traces: GET  /api/v2/apm/...
- deploys:read from GitHub Actions deployment events or our own deploy
          ledger.

For now this file raises NotImplementedError on each method so test setups
that accidentally select 'datadog' fail loudly rather than silently doing
nothing. v1 work is tracked in GitHub issues.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import ClassVar

from sre_agent.providers.base import DataProvider
from sre_agent.schemas import (
    DeploysEvidence,
    LogsEvidence,
    MetricsEvidence,
    TracesEvidence,
)


class DatadogProvider(DataProvider):
    """v1 — real Datadog. STUB."""

    name: ClassVar[str] = "datadog"

    def __init__(self) -> None:
        self.api_key = os.environ.get("DD_API_KEY")
        self.app_key = os.environ.get("DD_APP_KEY")
        self.site = os.environ.get("DD_SITE", "datadoghq.com")
        if not (self.api_key and self.app_key):
            raise RuntimeError(
                "DatadogProvider requires DD_API_KEY and DD_APP_KEY env vars."
            )

    def fetch_logs(self, **kwargs) -> LogsEvidence:  # type: ignore[override]
        raise NotImplementedError("v1 work — see GitHub issue.")

    def fetch_metrics(self, **kwargs) -> MetricsEvidence:  # type: ignore[override]
        raise NotImplementedError("v1 work — see GitHub issue.")

    def fetch_traces(self, **kwargs) -> TracesEvidence:  # type: ignore[override]
        raise NotImplementedError("v1 work — see GitHub issue.")

    def fetch_deploys(self, **kwargs) -> DeploysEvidence:  # type: ignore[override]
        raise NotImplementedError("v1 work — see GitHub issue.")
