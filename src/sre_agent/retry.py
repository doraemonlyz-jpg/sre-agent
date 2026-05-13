"""
Tiny retry helper for LLM invocations.

Why not just `tenacity`:

  We already pull a lot of deps. The retry pattern we need is 30 lines and
  has zero state — `tenacity` is overkill. If we ever need jitter buckets
  or async retries, we'll switch.

What we retry:

  * Connection / timeout / 5xx-shaped errors. The matcher errs on the side
    of retrying — `provider.RateLimit`, `httpx.TimeoutException`,
    `httpx.ConnectError`, anything whose class name contains "Timeout" /
    "Connection" / "Service" / "RateLimit".
  * Two attempts max (so total = 3 calls worst case). Past that the
    fallback path in the calling agent kicks in.

What we DON'T retry:

  * Pydantic validation errors — those won't fix themselves.
  * Auth errors — same.
  * Empty-content responses — those go into the agent's own fallback path.

Every retry is recorded as a `record_retry` event in the harness so you
can answer "how flaky is provider X today?" from `/api/harness/calls`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from sre_agent.harness import record_retry
from sre_agent.logging import get_logger

log = get_logger("retry")

T = TypeVar("T")


_RETRYABLE_TOKENS = (
    "timeout",
    "timedout",
    "timed out",
    "connection",
    "connectionerror",
    "ratelimit",
    "rate limit",
    "service unavailable",
    "serviceunavailable",
    "internalservererror",
    "internal server error",
    "502",
    "503",
    "504",
)


def is_retryable(exc: BaseException) -> bool:
    s = (type(exc).__name__ + " " + str(exc)).lower()
    return any(tok in s for tok in _RETRYABLE_TOKENS)


def with_retries(
    fn: Callable[[], T],
    *,
    agent: str,
    max_attempts: int = 2,
    base_delay_s: float = 0.4,
    incident_id: str | None = None,
) -> T:
    """
    Run `fn()` with up to `max_attempts` retries on retryable exceptions.

    `max_attempts` = number of *retries after* the first try, so the total
    call count is `1 + max_attempts`. With max_attempts=2 you'll see 1, 2,
    or 3 calls in the harness — easy to grep for.
    """
    last_exc: BaseException | None = None
    for attempt in range(max_attempts + 1):
        try:
            return fn()
        except BaseException as exc:
            last_exc = exc
            if attempt >= max_attempts or not is_retryable(exc):
                raise
            delay = base_delay_s * (2**attempt)
            record_retry(
                agent=agent,
                attempt=attempt + 1,
                error=type(exc).__name__ + ": " + str(exc)[:160],
                incident_id=incident_id,
            )
            log.warning(
                "llm.retry",
                agent=agent,
                attempt=attempt + 1,
                max_attempts=max_attempts,
                delay_s=round(delay, 2),
                error=type(exc).__name__,
            )
            time.sleep(delay)
    # Unreachable, but keeps mypy happy:
    raise last_exc  # type: ignore[misc]
