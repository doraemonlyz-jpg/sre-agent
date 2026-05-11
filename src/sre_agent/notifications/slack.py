"""
SlackNotifier — posts a diagnosed incident to a Slack channel.

Two modes:

* **Real**: SLACK_WEBHOOK_URL points at an incoming-webhook URL. We POST
  Slack Block Kit JSON. Returns SlackResult(sent=True, status=200).

* **Dry-run**: webhook URL missing, or SRE_SLACK_DRY_RUN=true. We build
  the same payload and return it inside the SlackResult, but don't hit
  the network. The dashboard surfaces this as a preview the user can
  copy into Slack themselves.

This split is deliberate — interview-time you might not have a live
Slack workspace handy, and we still want the formatting to be testable.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("sre_agent.notifications.slack")


@dataclass
class SlackResult:
    """What happened when we tried to post."""

    sent: bool
    dry_run: bool
    status: int | None = None
    error: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    preview: str = ""


# Severity → emoji prefix. Slack-compatible.
_SEV_EMOJI = {
    "SEV-1": ":rotating_light:",
    "SEV-2": ":warning:",
    "SEV-3": ":large_yellow_circle:",
    "SEV-4": ":information_source:",
}


class SlackNotifier:
    """Posts incident summaries. Construct via `from_env()` in the dashboard."""

    def __init__(
        self,
        webhook_url: str | None = None,
        *,
        dry_run: bool | None = None,
        client: httpx.Client | None = None,
        timeout_s: float = 5.0,
    ) -> None:
        self.webhook_url = webhook_url
        self.dry_run = dry_run if dry_run is not None else not bool(webhook_url)
        # Allow tests to inject a client so respx can hook in.
        self._client = client or httpx.Client(timeout=timeout_s)
        self._owns_client = client is None

    @classmethod
    def from_env(cls) -> SlackNotifier:
        """Read SLACK_WEBHOOK_URL + SRE_SLACK_DRY_RUN from process env."""
        url = os.environ.get("SLACK_WEBHOOK_URL") or None
        force_dry = (os.environ.get("SRE_SLACK_DRY_RUN", "").lower() in {"1", "true", "yes"})
        return cls(webhook_url=url, dry_run=force_dry or not url)

    # ─────────────────────────────────────────────────────────────────
    # public API
    # ─────────────────────────────────────────────────────────────────

    def post_incident(self, incident: dict[str, Any]) -> SlackResult:
        """Post a dashboard-shape incident dict (the legacy adapter shape)."""
        payload = self._build_payload(incident)
        preview = self._build_preview(incident)
        if self.dry_run or not self.webhook_url:
            return SlackResult(
                sent=False,
                dry_run=True,
                payload=payload,
                preview=preview,
            )
        try:
            r = self._client.post(self.webhook_url, json=payload)
            r.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("slack post failed: %s", e)
            return SlackResult(
                sent=False,
                dry_run=False,
                error=str(e),
                payload=payload,
                preview=preview,
            )
        return SlackResult(
            sent=True,
            dry_run=False,
            status=r.status_code,
            payload=payload,
            preview=preview,
        )

    # ─────────────────────────────────────────────────────────────────
    # rendering — pure, easy to test
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_preview(inc: dict[str, Any]) -> str:
        """Plain-text preview shown in the dashboard (no Slack markup needed)."""
        alert = inc.get("alert") or {}
        h = inc.get("hypothesis") or {}
        diag_ms = inc.get("diagnosis_ms") or 0
        rem_count = len(inc.get("remediation") or [])
        sev = alert.get("severity", "SEV-?")
        prefix = _SEV_EMOJI.get(sev, ":mega:")
        lines = [
            f"{prefix} *{alert.get('service', 'unknown')}* {sev}",
            f"_{alert.get('description', '')}_",
            "",
        ]
        if h:
            conf = int((h.get("confidence") or 0) * 100)
            lines += [
                f"*Top hypothesis* ({conf}%):",
                f"> {h.get('top', '(none)')}",
                "",
            ]
        lines += [
            f"*Diagnosed in*: {diag_ms / 1000:.1f}s",
            f"*Remediation*: {rem_count} action(s) ranked — see dashboard",
        ]
        return "\n".join(lines)

    @classmethod
    def _build_payload(cls, inc: dict[str, Any]) -> dict[str, Any]:
        """Slack Block Kit JSON. Posted verbatim to the webhook URL."""
        alert = inc.get("alert") or {}
        h = inc.get("hypothesis") or {}
        rem = inc.get("remediation") or []
        sev = alert.get("severity", "SEV-?")
        prefix = _SEV_EMOJI.get(sev, ":mega:")

        header = f"{prefix} {alert.get('service', 'unknown')} · {sev}"
        blocks: list[dict[str, Any]] = [
            {"type": "header", "text": {"type": "plain_text", "text": header[:150]}},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"_{alert.get('description', '')}_"},
            },
        ]
        if h:
            conf = int((h.get("confidence") or 0) * 100)
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Top hypothesis* ({conf}%):\n> {h.get('top', '(none)')}",
                    },
                }
            )
        if rem:
            top = rem[0]
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Suggested first action* (risk: {top.get('risk', '?')}):\n"
                            f"```{top.get('command', '')[:300]}```\n"
                            f"_{top.get('why', '')[:240]}_"
                        ),
                    },
                }
            )

        diag_ms = inc.get("diagnosis_ms") or 0
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"Diagnosed in *{diag_ms / 1000:.1f}s* · "
                            f"{len(rem)} remediation step(s) — full report in the dashboard."
                        ),
                    }
                ],
            }
        )
        return {"blocks": blocks, "text": cls._build_preview(inc)}

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> SlackNotifier:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
