"""
Inbound webhook adapters.

Each adapter normalizes an upstream alerting platform's payload into our
internal `AlertIn` schema, so the LangGraph runs the same way regardless
of who tripped the alert.

Public entry point: `parse_alert(payload, source=None)`.
"""

from sre_agent.webhooks.adapters import (
    UnknownPayloadError,
    from_datadog_monitor,
    from_generic,
    from_pagerduty,
    parse_alert,
)

__all__ = [
    "UnknownPayloadError",
    "from_datadog_monitor",
    "from_generic",
    "from_pagerduty",
    "parse_alert",
]
