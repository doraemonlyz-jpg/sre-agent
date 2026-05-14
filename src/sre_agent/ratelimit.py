"""
Token-bucket rate limiter.

Why a separate limiter on top of the bounded worker pool:

  * The worker pool absorbs *queued work*. The limiter prevents the queue
    from being filled by a hostile client in the first place. Without
    it, anyone can POST /api/incidents/fire 10k/s and DoS the LLM
    backend through the queue.

  * Rate limits are *per-key* — we limit by `bearer_token_name` if auth
    is on, else by `remote_addr`. This way a misbehaving caller never
    starves a well-behaved one.

Design choices:

  * Pure in-process token bucket. Replace with Redis (one Lua script)
    for multi-replica deployments.
  * Buckets are dataclasses with `capacity` (burst tolerance) and
    `refill_per_sec`. Default is 10 requests/sec with burst of 20.
  * Limits are configured per-endpoint group via env:
      SRE_RATE_FIRE=10:20      → 10/s sustained, burst 20
      SRE_RATE_BURST=1:2       → bursts are themselves rate-limited harder
      SRE_RATE_FEEDBACK=20:40
    Defaults are tuned for "single oncall engineer, normal use".
  * Master switch `SRE_RATE_LIMIT=off` disables (default: on).
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps


def _enabled() -> bool:
    val = os.environ.get("SRE_RATE_LIMIT", "on").strip().lower()
    return val in {"on", "1", "true", "yes"}


def _parse_rate(env_var: str, default: tuple[float, float]) -> tuple[float, float]:
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return default
    try:
        rate_s, burst_s = raw.split(":")
        return float(rate_s), float(burst_s)
    except ValueError:
        return default


# Sensible defaults: (refill_per_sec, burst_capacity)
DEFAULT_RATES: dict[str, tuple[float, float]] = {
    "fire":     (10.0, 20.0),
    "burst":    (1.0, 2.0),
    "feedback": (20.0, 40.0),
    "webhook":  (50.0, 100.0),
    "default":  (30.0, 60.0),
}


def rate_for(endpoint: str) -> tuple[float, float]:
    env_var = f"SRE_RATE_{endpoint.upper()}"
    default = DEFAULT_RATES.get(endpoint, DEFAULT_RATES["default"])
    return _parse_rate(env_var, default)


@dataclass
class _Bucket:
    capacity: float
    refill_per_sec: float
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

    def take(self, n: float = 1.0) -> bool:
        """Returns True if `n` tokens were available and consumed."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
        self.last_refill = now
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False


class RateLimiter:
    """Per-(endpoint, caller) buckets, thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        # Counters surfaced via /api/harness/summary or similar
        self.allowed_total = 0
        self.rejected_total = 0

    def _bucket(self, endpoint: str, caller: str) -> _Bucket:
        key = (endpoint, caller)
        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                refill, cap = rate_for(endpoint)
                b = _Bucket(capacity=cap, refill_per_sec=refill, tokens=cap)
                self._buckets[key] = b
            return b

    def check(self, endpoint: str, caller: str = "default") -> bool:
        if not _enabled():
            self.allowed_total += 1
            return True
        ok = self._bucket(endpoint, caller).take()
        with self._lock:
            if ok:
                self.allowed_total += 1
            else:
                self.rejected_total += 1
        if not ok:
            # Prometheus (B1): only the drop is interesting; allowed
            # traffic is already counted via the request handler's normal
            # metrics path.
            try:
                from sre_agent import metrics as _m
                _m.record_rate_limit_drop(scope=endpoint)
            except Exception:
                pass
        return ok

    def stats(self) -> dict:
        with self._lock:
            return {
                "enabled": _enabled(),
                "buckets": len(self._buckets),
                "allowed_total": self.allowed_total,
                "rejected_total": self.rejected_total,
            }

    def reset(self) -> None:
        """Test hook."""
        with self._lock:
            self._buckets.clear()
            self.allowed_total = 0
            self.rejected_total = 0


LIMITER = RateLimiter()


# ──────────────────────────────────────────────────────────────────────────
# Flask decorator
# ──────────────────────────────────────────────────────────────────────────


def _caller_key() -> str:
    """Per-token if auth is on; else per-IP. Keeps a misbehaving caller
    from starving everyone else on the same shared replica."""
    try:
        from flask import g, request

        tok = getattr(g, "auth_token", None)
        if tok is not None:
            return f"tok:{tok.name}"
        return f"ip:{request.remote_addr or 'unknown'}"
    except Exception:
        return "default"


def require(endpoint: str) -> Callable:
    """Flask decorator. Returns 429 with `Retry-After: 1` on rejection."""

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not LIMITER.check(endpoint, _caller_key()):
                from flask import jsonify

                resp = jsonify(
                    {
                        "error": "rate limit exceeded",
                        "endpoint": endpoint,
                        "retry_after_s": 1,
                    }
                )
                resp.status_code = 429
                resp.headers["Retry-After"] = "1"
                return resp
            return fn(*args, **kwargs)

        return wrapper

    return decorator
