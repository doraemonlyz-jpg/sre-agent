"""Data providers — abstraction over Datadog / GitHub / k8s so the graph never
talks to a real API directly. Mock provider for dev/CI; real Datadog provider
for prod (v1+)."""

from __future__ import annotations

from sre_agent.providers.base import DataProvider
from sre_agent.providers.mock import MockProvider

__all__ = ["DataProvider", "MockProvider", "get_provider"]


def get_provider(name: str | None = None) -> DataProvider:
    """
    Factory. Selects a provider based on env var SRE_DATA_PROVIDER
    (default: "mock"). Raises if asked for one that isn't installed.
    """
    import os

    provider = (name or os.environ.get("SRE_DATA_PROVIDER", "mock")).lower()

    if provider == "mock":
        return MockProvider()

    if provider == "datadog":
        # Lazy import: only import if explicitly requested.
        try:
            from sre_agent.providers.datadog import DatadogProvider
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "DatadogProvider requires the `datadog-api-client` package. "
                "Install it or set SRE_DATA_PROVIDER=mock."
            ) from e
        return DatadogProvider()

    raise ValueError(f"Unknown SRE_DATA_PROVIDER: {provider!r}. Use 'mock' or 'datadog'.")
