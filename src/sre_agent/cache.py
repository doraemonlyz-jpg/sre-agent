"""
Response cache for incident pipelines.

Why we cache:

  A real production alert pipe ("checkout-api error_rate > 5%") often
  re-fires every 30-60s while the issue is still active. Without a cache
  the agent would run the full 7-node graph N times for the same incident,
  burning $10-30 per minute on premium models and creating a thundering
  herd on Datadog / Prometheus.

  In prod, dedup is normally handled upstream (PagerDuty grouping rules),
  but defense in depth: we also dedup *inside* the agent so a misconfigured
  alerting rule can't bankrupt us.

How we cache:

  * Key  = `sha1(service ‖ severity ‖ normalize(description))[:16]`
  * TTL  = `SRE_CACHE_TTL_SECONDS`, default 300s (5 min)
  * Value = the entire INCIDENTS dict entry (phase, findings, hypothesis,
            remediation, events).

On a hit we return the cached `incident_id` so the dashboard can render
the same conclusion without re-running anything. The hit/miss event is
recorded in the harness so you can answer "what % of incidents did we
satisfy from cache?".

Thread-safe. In-process. Replace with Redis in production by swapping the
backing dict for a `redis.Redis` client — public API stays the same.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from sre_agent.harness import record_cache_event


def _ttl_seconds() -> float:
    try:
        return float(os.environ.get("SRE_CACHE_TTL_SECONDS", "300"))
    except ValueError:
        return 300.0


_WHITESPACE_RE = re.compile(r"\s+")
_DIGITS_RE = re.compile(r"\d+")


def _normalize_description(desc: str | None) -> str:
    """
    Strip noise that wouldn't change the incident's identity.

    `error_rate=0.07 sustained for 12s` and `error_rate=0.09 sustained for 18s`
    should collapse to the same cache key — same alert, just newer reading.
    We blank out digits and collapse whitespace; everything else stays.
    """
    if not desc:
        return ""
    s = desc.strip().lower()
    s = _DIGITS_RE.sub("N", s)
    s = _WHITESPACE_RE.sub(" ", s)
    return s[:200]


def cache_key(service: str, severity: str, description: str | None) -> str:
    """Stable 16-char key — short enough to log, wide enough to avoid collisions."""
    raw = f"{service.lower()}|{severity.upper()}|{_normalize_description(description)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class _Entry:
    incident_id: str
    payload: dict[str, Any]
    stored_at: float


@dataclass
class IncidentCache:
    """Thread-safe TTL cache for incident outcomes."""

    _lock: threading.RLock = field(default_factory=threading.RLock)
    _store: dict[str, _Entry] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    inserts: int = 0
    evictions: int = 0

    # ── public API ───────────────────────────────────────────────────

    def get(self, key: str) -> tuple[str, dict[str, Any]] | None:
        """Return `(incident_id, payload_copy)` or None on miss/expired."""
        ttl = _ttl_seconds()
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            if now - entry.stored_at > ttl:
                del self._store[key]
                self.evictions += 1
                self.misses += 1
                return None
            self.hits += 1
            return entry.incident_id, dict(entry.payload)

    def put(self, key: str, incident_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._store[key] = _Entry(
                incident_id=incident_id, payload=dict(payload), stored_at=time.time()
            )
            self.inserts += 1

    def invalidate(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                self.evictions += 1
                return True
            return False

    def sweep(self) -> int:
        """Drop expired entries. Returns count dropped."""
        ttl = _ttl_seconds()
        now = time.time()
        dropped = 0
        with self._lock:
            stale = [k for k, e in self._store.items() if now - e.stored_at > ttl]
            for k in stale:
                del self._store[k]
                dropped += 1
                self.evictions += 1
        return dropped

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            return {
                "size": len(self._store),
                "hits": self.hits,
                "misses": self.misses,
                "inserts": self.inserts,
                "evictions": self.evictions,
                "hit_rate": round(self.hits / total, 3) if total else 0.0,
                "ttl_seconds": _ttl_seconds(),
            }

    def reset(self) -> None:
        with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0
            self.inserts = 0
            self.evictions = 0


# Process-wide singleton.
CACHE = IncidentCache()


# ──────────────────────────────────────────────────────────────────────────
# Helpers wrapping the recorder so callers don't have to import harness.
# ──────────────────────────────────────────────────────────────────────────


def try_get(
    service: str,
    severity: str,
    description: str | None,
    *,
    record_event: bool = True,
) -> tuple[str, dict[str, Any]] | None:
    """Convenience: returns cached entry + records a `cache_hit`/`cache_miss` event."""
    key = cache_key(service, severity, description)
    found = CACHE.get(key)
    if record_event:
        if found is None:
            record_cache_event(hit=False, cache_key=key)
        else:
            cached_id, _payload = found
            record_cache_event(hit=True, incident_id=cached_id, cache_key=key)
    return found


def store(
    service: str,
    severity: str,
    description: str | None,
    incident_id: str,
    payload: dict[str, Any],
) -> str:
    """Convenience: returns the key used so callers can log it."""
    key = cache_key(service, severity, description)
    CACHE.put(key, incident_id, payload)
    return key
