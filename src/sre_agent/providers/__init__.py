"""
Data providers — abstraction over Datadog / Prometheus / Loki / etc. so the
graph never talks to a real observability API directly. Mock provider for
dev/CI; real providers for prod.

Provider matrix:

    name                    | logs   | metrics    | traces  | deploys
    ────────────────────────┼────────┼────────────┼─────────┼────────
    mock                    |   ✓    |    ✓       |   ✓     |   ✓
    datadog                 |   ✓    |    ✓       |   ✓     |   ✓
    prometheus              |   —    |    ✓       |   —     |   —
    loki                    |   ✓    |    —       |   —     |   —
    oss (composite: prom+loki)|   ✓    |    ✓       |   —     |   —

Selecting one via env:

    SRE_DATA_PROVIDER=mock            # default
    SRE_DATA_PROVIDER=datadog         # needs DD_API_KEY / DD_APP_KEY
    SRE_DATA_PROVIDER=oss             # Prometheus + Loki (demo-stack)
    SRE_DATA_PROVIDER=prometheus      # metrics-only
    SRE_DATA_PROVIDER=loki            # logs-only
"""

from __future__ import annotations

from sre_agent.providers.base import DataProvider
from sre_agent.providers.composite import CompositeProvider
from sre_agent.providers.mock import MockProvider

__all__ = [
    "CompositeProvider",
    "DataProvider",
    "MockProvider",
    "get_provider",
]


def get_provider(name: str | None = None) -> DataProvider:
    """
    Factory. Selects a provider based on env var SRE_DATA_PROVIDER
    (default: 'mock').
    """
    import os

    provider = (name or os.environ.get("SRE_DATA_PROVIDER", "mock")).lower()

    if provider == "mock":
        return MockProvider()

    if provider == "datadog":
        from sre_agent.providers.datadog import DatadogProvider
        return DatadogProvider()

    if provider == "prometheus":
        from sre_agent.providers.prometheus import PrometheusProvider
        return PrometheusProvider()

    if provider == "loki":
        from sre_agent.providers.loki import LokiProvider
        return LokiProvider()

    if provider in {"oss", "opensource", "open-source", "prom+loki"}:
        # Open-source stack — metrics from Prometheus, logs from Loki.
        # Traces and deploys remain NO_SIGNAL (no Tempo wiring yet).
        from sre_agent.providers.loki import LokiProvider
        from sre_agent.providers.prometheus import PrometheusProvider
        return CompositeProvider(
            metrics=PrometheusProvider(),
            logs=LokiProvider(),
        )

    raise ValueError(
        f"Unknown SRE_DATA_PROVIDER: {provider!r}. "
        "Use 'mock', 'datadog', 'prometheus', 'loki', or 'oss'."
    )
