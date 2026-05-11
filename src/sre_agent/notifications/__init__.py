"""Outbound notification adapters (Slack, future: PagerDuty acks, etc.)."""

from sre_agent.notifications.slack import SlackNotifier, SlackResult

__all__ = ["SlackNotifier", "SlackResult"]
