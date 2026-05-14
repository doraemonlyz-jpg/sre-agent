"""Outbound notification adapters: Slack (FYI) and PagerDuty (paging)."""

from sre_agent.notifications.pagerduty import (
    PagerDutyNotifier,
    PagerDutyResult,
)
from sre_agent.notifications.slack import SlackNotifier, SlackResult

__all__ = [
    "SlackNotifier",
    "SlackResult",
    "PagerDutyNotifier",
    "PagerDutyResult",
]
