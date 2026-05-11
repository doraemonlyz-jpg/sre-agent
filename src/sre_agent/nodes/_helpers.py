"""Shared utilities used by all agent nodes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def make_event(agent: str, kind: str, message: str, **extra: Any) -> dict[str, Any]:
    """Build a uniform event dict for the live activity feed."""
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "kind": kind,  # "started" | "tool" | "evidence" | "done" | "error"
        "message": message,
        **extra,
    }
