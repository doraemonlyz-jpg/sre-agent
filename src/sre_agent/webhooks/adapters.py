"""
Webhook payload adapters: external alert → AlertIn.

We support three sources out of the box:

* **datadog**:    Datadog Monitor → Webhook integration. The default
                  variable-substituted JSON ($SERVICE, $ALERT_TITLE, ...).
* **pagerduty**:  PagerDuty Webhook v3 envelope (event.event_type=
                  'incident.triggered').
* **generic**:    a flat shape we document for anyone else. Useful for
                  Prometheus Alertmanager → a tiny shim, or curl-based
                  smoke tests.

Sniffing strategy: if the caller tells us which source it is (via an
explicit `source` param or `X-SRE-Source` header), we use that. Otherwise
we look at the shape of the payload.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sre_agent.schemas import AlertIn, Severity


class UnknownPayloadError(ValueError):
    """Raised when we can't figure out which adapter to use."""


# ──────────────────────────────────────────────────────────────────────────
# severity normalization
# ──────────────────────────────────────────────────────────────────────────

# Map common external severity strings to our 4-level scale.
_SEV_ALIASES: dict[str, Severity] = {
    # Datadog priorities
    "p1": Severity.SEV_1, "p2": Severity.SEV_2, "p3": Severity.SEV_3, "p4": Severity.SEV_4,
    # PagerDuty
    "high": Severity.SEV_1, "low": Severity.SEV_3,
    "critical": Severity.SEV_1, "error": Severity.SEV_2, "warning": Severity.SEV_3,
    "info": Severity.SEV_4, "informational": Severity.SEV_4,
    # SEV-N shorthand
    "sev-1": Severity.SEV_1, "sev-2": Severity.SEV_2,
    "sev-3": Severity.SEV_3, "sev-4": Severity.SEV_4,
    "sev1": Severity.SEV_1, "sev2": Severity.SEV_2,
    "sev3": Severity.SEV_3, "sev4": Severity.SEV_4,
}


def _norm_severity(raw: Any, default: Severity = Severity.SEV_2) -> Severity:
    if not raw:
        return default
    key = str(raw).strip().lower()
    return _SEV_ALIASES.get(key, default)


def _norm_ts(raw: Any) -> datetime:
    """Parse various timestamp formats; fall back to now() if we can't."""
    if not raw:
        return datetime.now(timezone.utc)
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    s = str(raw).strip()
    # Try ISO 8601 first.
    try:
        # Datadog's $LAST_TRIGGERED_AT is like "2024-01-15T18:23:01.123Z"
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    # Unix seconds?
    try:
        return datetime.fromtimestamp(float(s), tz=timezone.utc)
    except (ValueError, OSError):
        pass
    return datetime.now(timezone.utc)


def _parse_tag_csv(raw: Any) -> list[str]:
    """Datadog passes tags as a comma-separated string. Normalize to a list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def _service_from_tags(tags: list[str]) -> str | None:
    for t in tags:
        if t.startswith("service:") and len(t) > len("service:"):
            return t.split(":", 1)[1]
    return None


# ──────────────────────────────────────────────────────────────────────────
# Datadog Monitor webhook
# ──────────────────────────────────────────────────────────────────────────


def from_datadog_monitor(payload: dict[str, Any]) -> AlertIn:
    """
    Parse a Datadog Monitor → Webhook payload.

    Recommended Datadog "Custom Payload":

        {
          "alert_id": "$ALERT_ID", "alert_status": "$ALERT_STATUS",
          "alert_title": "$ALERT_TITLE", "alert_metric": "$ALERT_METRIC",
          "priority": "$ALERT_PRIORITY", "service": "$SERVICE",
          "tags": "$TAGS", "date": "$LAST_TRIGGERED_AT",
          "event_msg": "$EVENT_MSG"
        }
    """
    tags = _parse_tag_csv(payload.get("tags"))
    service = (
        payload.get("service")
        or _service_from_tags(tags)
        or "unknown"
    )
    severity = _norm_severity(payload.get("priority") or payload.get("severity"))
    description = (
        payload.get("alert_title")
        or payload.get("event_title")
        or payload.get("event_msg")
        or "Datadog alert"
    )
    return AlertIn(
        service=service,
        severity=severity,
        description=str(description)[:400],
        started_at=_norm_ts(payload.get("date") or payload.get("last_triggered_at")),
        tags=tags,
    )


# ──────────────────────────────────────────────────────────────────────────
# PagerDuty Webhook v3
# ──────────────────────────────────────────────────────────────────────────


def from_pagerduty(payload: dict[str, Any]) -> AlertIn:
    """
    Parse a PagerDuty v3 webhook. Envelope shape:

        {"event": {"event_type": "incident.triggered",
                   "data": {"title": "...", "service": {"summary": "..."},
                            "urgency": "high", "created_at": "...",
                            "details": {...}}}}
    """
    event = payload.get("event") or {}
    data = event.get("data") or {}
    service_block = data.get("service") or {}
    service = (
        (service_block.get("summary") if isinstance(service_block, dict) else None)
        or data.get("service_name")
        or "unknown"
    )
    severity = _norm_severity(data.get("urgency") or data.get("priority"))
    description = data.get("title") or data.get("summary") or "PagerDuty incident"

    raw_tags: list[str] = []
    for t in (data.get("teams") or []):
        if isinstance(t, dict) and t.get("summary"):
            raw_tags.append(f"team:{t['summary']}")

    return AlertIn(
        service=str(service),
        severity=severity,
        description=str(description)[:400],
        started_at=_norm_ts(data.get("created_at")),
        tags=raw_tags,
    )


# ──────────────────────────────────────────────────────────────────────────
# Generic webhook — documented contract
# ──────────────────────────────────────────────────────────────────────────


def from_generic(payload: dict[str, Any]) -> AlertIn:
    """
    Documented "send-us-whatever" shape, useful for curl/Alertmanager.

    Required:
        service:      str
        description:  str

    Optional:
        severity:  one of SEV-1..SEV-4, P1..P4, critical/high/etc. (default SEV-2)
        started_at: ISO 8601 or unix seconds (default now)
        tags:       list[str] or "k:v,k:v" string
    """
    if "service" not in payload or "description" not in payload:
        raise UnknownPayloadError(
            "generic payload must include 'service' and 'description' fields"
        )
    return AlertIn(
        service=str(payload["service"]),
        severity=_norm_severity(payload.get("severity")),
        description=str(payload["description"])[:400],
        started_at=_norm_ts(payload.get("started_at")),
        tags=_parse_tag_csv(payload.get("tags")),
    )


# ──────────────────────────────────────────────────────────────────────────
# Sniffing
# ──────────────────────────────────────────────────────────────────────────


def _sniff(payload: dict[str, Any]) -> str:
    """
    Return the adapter name we think fits this payload.

    Order matters — we go from most-distinctive to least.
    """
    # PagerDuty v3 envelope is unmistakable.
    ev = payload.get("event")
    if isinstance(ev, dict) and isinstance(ev.get("data"), dict) and "event_type" in ev:
        return "pagerduty"
    # Datadog-specific keys.
    if any(k in payload for k in ("alert_id", "alert_title", "alert_status", "alert_metric")):
        return "datadog"
    # Generic — accept iff it has the documented required keys.
    if "service" in payload and "description" in payload:
        return "generic"
    raise UnknownPayloadError(
        "could not detect webhook source; pass ?source=datadog|pagerduty|generic "
        "or include an X-SRE-Source header"
    )


def parse_alert(
    payload: dict[str, Any],
    *,
    source: str | None = None,
) -> AlertIn:
    """
    Single entry point used by the Flask endpoint.

    `source` (optional) forces a specific adapter. Otherwise we sniff.
    """
    src = (source or _sniff(payload)).lower()
    if src == "datadog":
        return from_datadog_monitor(payload)
    if src == "pagerduty":
        return from_pagerduty(payload)
    if src == "generic":
        return from_generic(payload)
    raise UnknownPayloadError(f"unknown source: {source!r}")
