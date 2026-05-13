"""
Slack interactive payload parser + HMAC verification.

When a user clicks a button on a Slack message, Slack POSTs a
form-encoded payload to our configured Request URL. This module:

  1. Verifies the request signature (HMAC-SHA256 of `v0:<ts>:<body>` with
     `SLACK_SIGNING_SECRET`). Without verification anyone who knows our
     URL can spoof feedback.
  2. Extracts the (action_id, incident_id, user) triple.
  3. Maps the action_id to a feedback verdict we can persist.

Why verification matters:

  Slack's interactive endpoint is a public webhook. If you skip
  verification, a curl from anywhere becomes "the oncall said the
  diagnosis was correct" — and an attacker can poison the feedback
  store / flywheel before you notice.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass

log = logging.getLogger("sre_agent.slack_actions")


SLACK_VERIFY_REQUIRED_ENV = "SRE_SLACK_VERIFY_REQUIRED"


def verify_required() -> bool:
    """
    Off by default during demos (so curl works), on in prod.
    Production deployments should set SRE_SLACK_VERIFY_REQUIRED=1.
    """
    return os.environ.get(SLACK_VERIFY_REQUIRED_ENV, "").lower() in {"1", "true", "yes", "on"}


def verify_signature(
    *,
    body: bytes,
    timestamp: str,
    signature: str,
    secret: str | None = None,
    max_age_s: int = 60 * 5,
) -> bool:
    """
    Returns True if the X-Slack-Signature matches. Implements the exact
    algorithm from
    https://api.slack.com/authentication/verifying-requests-from-slack.
    """
    secret = secret or os.environ.get("SLACK_SIGNING_SECRET")
    if not secret:
        return False
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(time.time() - ts) > max_age_s:
        return False  # replay protection
    base = f"v0:{timestamp}:".encode() + body
    expected = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


# Mapping from Slack action_id → feedback record
_VERDICT_FOR_ACTION = {
    "sre_feedback_up":    "thumbs_up",
    "sre_feedback_down":  "thumbs_down",
    "sre_mark_falsepos":  "incorrect",
}


_TAG_FOR_ACTION = {
    "sre_mark_falsepos":  ["false-positive"],
}


@dataclass
class ParsedAction:
    incident_id: str
    action_id: str
    verdict: str
    user_id: str
    user_name: str
    response_url: str | None
    tags: list[str]


class SlackActionError(Exception):
    """Raised when the payload is malformed enough that we can't do anything."""


def parse_payload(form: Mapping[str, str]) -> ParsedAction:
    """
    Slack POSTs `payload=<urlencoded-json>`. We pluck the first action
    out, validate the shape, and return the normalized record.
    """
    raw = form.get("payload")
    if not raw:
        raise SlackActionError("missing 'payload' field")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SlackActionError(f"payload is not JSON: {e}") from e

    actions = data.get("actions") or []
    if not actions:
        raise SlackActionError("no actions in payload")

    a = actions[0]
    action_id = a.get("action_id") or ""
    if action_id not in _VERDICT_FOR_ACTION:
        raise SlackActionError(f"unknown action_id: {action_id!r}")

    incident_id = a.get("value") or ""
    if not incident_id:
        raise SlackActionError("action has no incident_id (value field)")

    user = data.get("user") or {}
    return ParsedAction(
        incident_id=incident_id,
        action_id=action_id,
        verdict=_VERDICT_FOR_ACTION[action_id],
        user_id=user.get("id", ""),
        user_name=user.get("username") or user.get("name") or "slack-user",
        response_url=data.get("response_url"),
        tags=_TAG_FOR_ACTION.get(action_id, []),
    )
