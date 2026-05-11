"""Structured logging setup. JSON for prod, friendly for dev."""

from __future__ import annotations

import logging
import os
import sys

import structlog


def setup_logging() -> None:
    """Idempotent. Reads SRE_LOG_LEVEL and SRE_LOG_JSON from env."""
    level = os.environ.get("SRE_LOG_LEVEL", "INFO").upper()
    use_json = os.environ.get("SRE_LOG_JSON", "false").lower() == "true"

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level, logging.INFO),
    )

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if use_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty()))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level, 20)),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name or "sre_agent")
