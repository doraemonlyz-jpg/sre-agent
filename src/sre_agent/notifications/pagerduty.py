"""
PagerDutyNotifier -- D4 PagerDuty Events API v2 integration.

Why a separate notifier
-----------------------
Slack notifications are great for "the team should know this happened"
but they're FYI-grade: nobody gets woken up. Real oncall flows pages
through PagerDuty (or OpsGenie / VictorOps -- same protocol shape).

This notifier owns three lifecycle events:

  * ``trigger``     -- a SEV-1 / SEV-2 incident was diagnosed; page oncall.
  * ``acknowledge`` -- oncall hit "Investigating" in the dashboard.
  * ``resolve``     -- the incident was resolved (manual or auto via
                       a downstream webhook).

The PagerDuty Events API v2 is an unauthenticated POST to a single
endpoint with a per-integration "routing key" and a stable
``dedup_key`` per incident. PagerDuty deduplicates triggers with the
same dedup_key so that alert flapping doesn't generate 50 pages.

Two modes (mirrors SlackNotifier)
---------------------------------
  * **Real**     -- ``PAGERDUTY_ROUTING_KEY`` set; we POST to
                    ``events.pagerduty.com``.
  * **Dry-run**  -- routing key missing OR ``SRE_PAGERDUTY_DRY_RUN=true``.
                    We build the payload and return it inside the
                    ``PagerDutyResult`` so dashboards / tests can assert
                    on the exact bytes that WOULD have been sent.

This split keeps the dashboard usable in interview demos with no
PagerDuty workspace.

Env vars
--------
    PAGERDUTY_ROUTING_KEY        integration key from a PD service
    PAGERDUTY_API_URL            override (defaults to events.pagerduty.com)
    PAGERDUTY_HTTP_TIMEOUT_S     default 5
    PAGERDUTY_MIN_SEVERITY       SEV-1 | SEV-2 | SEV-3 | SEV-4 (default SEV-2)
    SRE_PAGERDUTY_DRY_RUN        true  -> never POST; build payload only
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

logger = logging.getLogger("sre_agent.notifications.pagerduty")


# Severity ordering used to gate which alerts page. SEV-1 / SEV-2 page;
# SEV-3 / SEV-4 are FYI-grade by default.
_SEV_RANK = {"SEV-1": 1, "SEV-2": 2, "SEV-3": 3, "SEV-4": 4}

# PagerDuty's own severity vocabulary (it doesn't accept SEV-1 directly).
_PD_SEVERITY: dict[str, str] = {
    "SEV-1": "critical",
    "SEV-2": "error",
    "SEV-3": "warning",
    "SEV-4": "info",
}

EventAction = Literal["trigger", "acknowledge", "resolve"]


@dataclass
class PagerDutyResult:
    sent: bool
    dry_run: bool
    event_action: EventAction
    dedup_key: str
    status: int | None = None
    error: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    pd_dedup_key_returned: str | None = None


class PagerDutyNotifier:
    """Sends incident lifecycle events to PagerDuty Events API v2.

    Construct via ``from_env()`` in the dashboard. Tests inject their
    own httpx client to mock the API at the transport level.
    """

    DEFAULT_API_URL = "https://events.pagerduty.com"

    def __init__(
        self,
        routing_key: str | None = None,
        *,
        dry_run: bool | None = None,
        api_url: str | None = None,
        client: httpx.Client | None = None,
        timeout_s: float = 5.0,
        min_severity: str = "SEV-2",
    ) -> None:
        self.routing_key = (
            routing_key
            or os.environ.get("PAGERDUTY_ROUTING_KEY", "").strip()
            or None
        )
        self.api_url = (
            api_url
            or os.environ.get("PAGERDUTY_API_URL")
            or self.DEFAULT_API_URL
        ).rstrip("/")
        # Dry-run if explicitly asked OR if we have no routing key. The
        # dashboard prefers no-routing-key + dry-run-implicit so a fresh
        # checkout works without any env setup.
        explicit_dry = (
            dry_run
            if dry_run is not None
            else os.environ.get("SRE_PAGERDUTY_DRY_RUN", "").lower() in ("1", "true", "yes")
        )
        self.dry_run = explicit_dry or self.routing_key is None
        self.timeout_s = float(
            os.environ.get("PAGERDUTY_HTTP_TIMEOUT_S", str(timeout_s))
        )
        self.min_severity = (
            os.environ.get("PAGERDUTY_MIN_SEVERITY", min_severity).upper()
        )
        self._client = client or (
            None if self.dry_run else httpx.Client(timeout=self.timeout_s)
        )

    # ── construction helper ─────────────────────────────────────────

    @classmethod
    def from_env(cls) -> "PagerDutyNotifier":
        return cls()

    # ── public API ──────────────────────────────────────────────────

    def trigger(
        self,
        *,
        incident_id: str,
        service: str,
        severity: str,
        summary: str,
        details: dict[str, Any] | None = None,
        source: str = "sre-agent",
    ) -> PagerDutyResult:
        """Page oncall. No-op if severity below min_severity."""
        if not self._severe_enough(severity):
            return PagerDutyResult(
                sent=False,
                dry_run=self.dry_run,
                event_action="trigger",
                dedup_key=incident_id,
                error=f"below min_severity={self.min_severity}",
            )
        payload = self._build_payload(
            event_action="trigger",
            dedup_key=incident_id,
            service=service,
            severity=severity,
            summary=summary,
            details=details or {},
            source=source,
        )
        return self._send(payload, "trigger", incident_id, severity)

    def acknowledge(self, *, incident_id: str) -> PagerDutyResult:
        """Mark the incident as acknowledged. Idempotent on PD's side."""
        payload = {
            "routing_key": self.routing_key or "DRY_RUN",
            "event_action": "acknowledge",
            "dedup_key": incident_id,
        }
        return self._send(payload, "acknowledge", incident_id, severity="N/A")

    def resolve(self, *, incident_id: str) -> PagerDutyResult:
        """Mark the incident as resolved."""
        payload = {
            "routing_key": self.routing_key or "DRY_RUN",
            "event_action": "resolve",
            "dedup_key": incident_id,
        }
        return self._send(payload, "resolve", incident_id, severity="N/A")

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    # ── implementation ──────────────────────────────────────────────

    def _severe_enough(self, severity: str) -> bool:
        sev = (severity or "").upper()
        cap = _SEV_RANK.get(self.min_severity, 2)
        return _SEV_RANK.get(sev, 5) <= cap

    def _build_payload(
        self,
        *,
        event_action: EventAction,
        dedup_key: str,
        service: str,
        severity: str,
        summary: str,
        details: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        return {
            "routing_key": self.routing_key or "DRY_RUN",
            "event_action": event_action,
            "dedup_key": dedup_key,
            "payload": {
                "summary": summary[:1024],  # PD enforces a 1024 char limit
                "source": source,
                "severity": _PD_SEVERITY.get(severity.upper(), "warning"),
                "component": service,
                "group": "sre-agent",
                "class": "automated-diagnosis",
                "custom_details": details,
            },
        }

    def _send(
        self,
        payload: dict[str, Any],
        action: EventAction,
        incident_id: str,
        severity: str,
    ) -> PagerDutyResult:
        if self.dry_run:
            self._record_metric(action, severity, "dry_run")
            return PagerDutyResult(
                sent=False,
                dry_run=True,
                event_action=action,
                dedup_key=incident_id,
                payload=payload,
            )

        assert self._client is not None  # narrow for type checker
        try:
            r = self._client.post(
                f"{self.api_url}/v2/enqueue",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        except Exception as e:
            logger.warning(
                "pagerduty.%s failed: %s", action, e, extra={"incident_id": incident_id},
            )
            self._record_metric(action, severity, f"error.{type(e).__name__.lower()}")
            return PagerDutyResult(
                sent=False,
                dry_run=False,
                event_action=action,
                dedup_key=incident_id,
                error=f"{type(e).__name__}: {str(e)[:160]}",
                payload=payload,
            )

        ok = 200 <= r.status_code < 300
        # PD echoes back its dedup_key on 202 success
        pd_dedup = None
        if ok:
            try:
                pd_dedup = r.json().get("dedup_key")
            except Exception:
                pass
        outcome = "ok" if ok else f"http_{r.status_code}"
        self._record_metric(action, severity, outcome)
        return PagerDutyResult(
            sent=ok,
            dry_run=False,
            event_action=action,
            dedup_key=incident_id,
            status=r.status_code,
            error=None if ok else f"http {r.status_code}: {r.text[:160]}",
            payload=payload,
            pd_dedup_key_returned=pd_dedup,
        )

    @staticmethod
    def _record_metric(action: str, severity: str, outcome: str) -> None:
        try:
            from sre_agent.metrics import PAGERDUTY_EVENTS_TOTAL
            PAGERDUTY_EVENTS_TOTAL.labels(
                event_type=action, severity=severity, outcome=outcome,
            ).inc()
        except Exception:
            pass
