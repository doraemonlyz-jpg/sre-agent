"""
Harness Engineering — L3/L4 capabilities for the SRE agent.

Where this fits in the maturity ladder (see DESIGN.md):

    L0  prompt-in-string
    L1  structured I/O  ............ schemas.py (Pydantic)
    L2  defense in depth ........... try/except + rule fallback + confidence gate
    L3  observability  ............. THIS FILE (call tracing) + scale.COUNTERS
    L4  eval harness  .............. tests/eval/
    L5  continuous improvement ..... A/B, DSPy compile, feedback flywheel

What this module gives you:

  * `LLMCallRecord` — one row per LLM invocation: agent, model, prompt_sha,
    latency, token counts, status. Stored in a thread-safe ring buffer
    (default 1000 rows, configurable via SRE_HARNESS_BUFFER).

  * `HarnessRecorder` — singleton that LangChain callbacks write into.
    Use `bind_incident()` as a context manager so calls inside a graph run
    get tagged with their incident_id automatically (LangChain callbacks
    don't carry our domain identifiers).

  * `record_persona_load(agent, sha)` — emit a tiny "metadata" record so
    you can answer "which prompt version was used for incident X".

  * `record_cache_event(...)` — feed in cache hit/miss for end-to-end
    accounting (also used by cache.py).

Why a separate module, not just more methods on `scale.COUNTERS`:

  * COUNTERS is monotonic aggregate state (counts/rates).
  * Harness records are *per-event* and indexed by incident — different
    storage shape, different concurrency profile, different query patterns.
  * Keeps the "production-scale mock" (scale.py) decoupled from the
    "engineering hygiene" layer (this file). Replacing either with the
    real production version (e.g. Prometheus + OpenTelemetry) is a
    single-module swap.
"""

from __future__ import annotations

import contextvars
import os
import threading
import time
import uuid
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from langchain_core.callbacks import BaseCallbackHandler

# ──────────────────────────────────────────────────────────────────────────
# Per-call record
# ──────────────────────────────────────────────────────────────────────────

RecordKind = Literal["llm_call", "persona_load", "cache_hit", "cache_miss", "retry"]


@dataclass
class LLMCallRecord:
    """One row in the harness ring buffer."""

    id: str
    kind: RecordKind
    ts: float
    agent: str = "?"
    incident_id: str | None = None
    # LLM-specific
    model: str | None = None
    role: str | None = None  # 'orchestrator' | 'worker'
    prompt_sha: str | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    status: Literal["ok", "error", "retry", "skipped"] = "ok"
    error: str | None = None
    # Free-form
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        # Drop empty detail to keep API payloads tight
        if not d["detail"]:
            d.pop("detail")
        return d


# ──────────────────────────────────────────────────────────────────────────
# Context propagation (incident_id + agent name)
#
# LangChain callbacks run inside `.invoke()`, which we call from inside an
# agent function. The callback can read these contextvars to tag the record.
# ──────────────────────────────────────────────────────────────────────────

_current_incident: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_incident", default=None
)
_current_agent: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_agent", default=None
)
_current_prompt_sha: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_prompt_sha", default=None
)


@contextmanager
def bind_incident(incident_id: str | None) -> Iterator[None]:
    """Set the active incident_id for any LLM calls inside this block."""
    token = _current_incident.set(incident_id)
    try:
        yield
    finally:
        _current_incident.reset(token)


@contextmanager
def bind_agent(agent_name: str, *, prompt_sha: str | None = None) -> Iterator[None]:
    """Set the active agent name + prompt sha for any LLM calls inside this block."""
    tok_a = _current_agent.set(agent_name)
    tok_s = _current_prompt_sha.set(prompt_sha)
    try:
        yield
    finally:
        _current_agent.reset(tok_a)
        _current_prompt_sha.reset(tok_s)


# ──────────────────────────────────────────────────────────────────────────
# Ring buffer
# ──────────────────────────────────────────────────────────────────────────


def _buffer_size() -> int:
    try:
        return max(100, int(os.environ.get("SRE_HARNESS_BUFFER", "1000")))
    except ValueError:
        return 1000


class HarnessRecorder:
    """
    Thread-safe ring buffer of `LLMCallRecord` + cheap incident index.

    We keep two structures:
      * `_records`     — bounded deque, last N records, global
      * `_by_incident` — dict[incident_id, list[record_id]] for fast lookup;
                         entries are also evicted as the ring rolls.

    For a real prod system this is OpenTelemetry + a backend like Tempo or
    Langfuse. The shape here matches what those tools expose, so swapping
    is a single-module change.
    """

    def __init__(self, max_records: int | None = None) -> None:
        self._lock = threading.RLock()
        self._max = max_records or _buffer_size()
        self._records: deque[LLMCallRecord] = deque(maxlen=self._max)
        self._by_incident: dict[str, list[str]] = {}

    # ── recording API ────────────────────────────────────────────────

    def record(self, rec: LLMCallRecord) -> None:
        with self._lock:
            # Evict the oldest record's incident index entry if we're full
            if len(self._records) == self._max and self._records:
                evicted = self._records[0]
                if evicted.incident_id and evicted.incident_id in self._by_incident:
                    try:
                        self._by_incident[evicted.incident_id].remove(evicted.id)
                        if not self._by_incident[evicted.incident_id]:
                            del self._by_incident[evicted.incident_id]
                    except ValueError:
                        pass
            self._records.append(rec)
            if rec.incident_id:
                self._by_incident.setdefault(rec.incident_id, []).append(rec.id)

    # ── query API ────────────────────────────────────────────────────

    def recent(self, limit: int = 50, *, kind: RecordKind | None = None) -> list[LLMCallRecord]:
        with self._lock:
            items = list(self._records)
        if kind:
            items = [r for r in items if r.kind == kind]
        return items[-limit:][::-1]

    def for_incident(self, incident_id: str) -> list[LLMCallRecord]:
        with self._lock:
            ids = self._by_incident.get(incident_id, [])
            id_set = set(ids)
            return [r for r in self._records if r.id in id_set]

    def summary(self) -> dict[str, Any]:
        """Aggregate stats for the /api/harness/summary endpoint."""
        with self._lock:
            records = list(self._records)
        if not records:
            return {
                "total_records": 0,
                "buffer_capacity": self._max,
                "incidents_tracked": 0,
            }
        by_kind: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_agent: dict[str, int] = {}
        total_lat = 0.0
        lat_n = 0
        total_in = 0
        total_out = 0
        for r in records:
            by_kind[r.kind] = by_kind.get(r.kind, 0) + 1
            by_status[r.status] = by_status.get(r.status, 0) + 1
            by_agent[r.agent] = by_agent.get(r.agent, 0) + 1
            if r.latency_ms is not None:
                total_lat += r.latency_ms
                lat_n += 1
            if r.input_tokens:
                total_in += r.input_tokens
            if r.output_tokens:
                total_out += r.output_tokens
        return {
            "total_records": len(records),
            "buffer_capacity": self._max,
            "incidents_tracked": len(self._by_incident),
            "by_kind": by_kind,
            "by_status": by_status,
            "by_agent": by_agent,
            "avg_latency_ms": round(total_lat / lat_n, 1) if lat_n else None,
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
        }

    def reset(self) -> None:
        """Test hook."""
        with self._lock:
            self._records.clear()
            self._by_incident.clear()


RECORDER = HarnessRecorder()


# ──────────────────────────────────────────────────────────────────────────
# LangChain callback that fills LLMCallRecord
#
# We replace the existing `_LlmCallCounter` with this richer one. The legacy
# `scale.COUNTERS.record_llm_call()` is still invoked so the live counter
# strip in the dashboard keeps working — defense in depth: both observability
# planes get fed from one source of truth.
# ──────────────────────────────────────────────────────────────────────────


class HarnessCallback(BaseCallbackHandler):
    """LangChain callback recording one LLMCallRecord per chat model call."""

    def __init__(self) -> None:
        # In-flight calls keyed by run_id so on_llm_end can find the record
        # we created in on_chat_model_start. Instance state (not class state)
        # so HARNESS_CALLBACK lives as a singleton without bleeding across
        # would-be instances.
        self._inflight: dict[str, LLMCallRecord] = {}

    def on_chat_model_start(  # type: ignore[override]
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        from sre_agent.scale import COUNTERS

        COUNTERS.record_llm_call()
        # Stash a wallclock so on_llm_end can compute latency.
        kwargs_meta = kwargs.get("metadata") or {}
        model = (
            kwargs_meta.get("ls_model_name")
            or (serialized or {}).get("name")
            or "?"
        )
        rec = LLMCallRecord(
            id=uuid.uuid4().hex[:12],
            kind="llm_call",
            ts=time.time(),
            agent=_current_agent.get() or "?",
            incident_id=_current_incident.get(),
            model=model,
            prompt_sha=_current_prompt_sha.get(),
            status="ok",
            detail={"_start": time.time()},
        )
        # Stash on the run so on_llm_end can find it
        self._inflight.setdefault(str(run_id), rec)
        RECORDER.record(rec)

    def on_llm_end(  # type: ignore[override]
        self, response: Any, *, run_id: Any = None, **kwargs: Any
    ) -> None:
        rec = self._inflight.pop(str(run_id), None)
        if rec is None:
            return
        start = rec.detail.get("_start") or rec.ts
        rec.latency_ms = round((time.time() - start) * 1000, 1)
        # Try to extract token usage from the response (provider-specific shapes)
        try:
            usage = None
            if hasattr(response, "llm_output") and isinstance(response.llm_output, dict):
                usage = response.llm_output.get("token_usage") or response.llm_output.get(
                    "usage"
                )
            if not usage and getattr(response, "generations", None):
                # Some providers stash usage on the first generation message
                gens = response.generations
                if gens and gens[0]:
                    msg = getattr(gens[0][0], "message", None)
                    if msg is not None:
                        usage = getattr(msg, "usage_metadata", None) or getattr(
                            msg, "response_metadata", {}
                        ).get("token_usage")
            if isinstance(usage, dict):
                rec.input_tokens = (
                    usage.get("prompt_tokens")
                    or usage.get("input_tokens")
                    or usage.get("prompt_token_count")
                )
                rec.output_tokens = (
                    usage.get("completion_tokens")
                    or usage.get("output_tokens")
                    or usage.get("candidates_token_count")
                )
        except Exception:
            # Token accounting is best-effort; don't break the call on parsing
            pass
        rec.detail.pop("_start", None)

    def on_llm_error(  # type: ignore[override]
        self, error: BaseException, *, run_id: Any = None, **kwargs: Any
    ) -> None:
        rec = self._inflight.pop(str(run_id), None)
        if rec is None:
            return
        start = rec.detail.get("_start") or rec.ts
        rec.latency_ms = round((time.time() - start) * 1000, 1)
        rec.status = "error"
        rec.error = type(error).__name__ + ": " + str(error)[:200]
        rec.detail.pop("_start", None)


# Singleton callback (LangChain expects callbacks to be reusable objects).
HARNESS_CALLBACK = HarnessCallback()


# ──────────────────────────────────────────────────────────────────────────
# Non-LLM event helpers
# ──────────────────────────────────────────────────────────────────────────


def record_persona_load(agent: str, sha: str, *, incident_id: str | None = None) -> None:
    """Emit a metadata record so we can answer 'which prompt version produced output X'."""
    RECORDER.record(
        LLMCallRecord(
            id=uuid.uuid4().hex[:12],
            kind="persona_load",
            ts=time.time(),
            agent=agent,
            incident_id=incident_id or _current_incident.get(),
            prompt_sha=sha,
            status="ok",
        )
    )


def record_cache_event(
    *,
    hit: bool,
    incident_id: str | None = None,
    cache_key: str | None = None,
    age_s: float | None = None,
) -> None:
    RECORDER.record(
        LLMCallRecord(
            id=uuid.uuid4().hex[:12],
            kind="cache_hit" if hit else "cache_miss",
            ts=time.time(),
            agent="cache",
            incident_id=incident_id,
            status="ok",
            detail={"cache_key": cache_key, "age_s": age_s} if (cache_key or age_s) else {},
        )
    )


def record_retry(
    *,
    agent: str,
    attempt: int,
    error: str,
    incident_id: str | None = None,
) -> None:
    RECORDER.record(
        LLMCallRecord(
            id=uuid.uuid4().hex[:12],
            kind="retry",
            ts=time.time(),
            agent=agent,
            incident_id=incident_id or _current_incident.get(),
            status="retry",
            error=error[:200],
            detail={"attempt": attempt},
        )
    )
