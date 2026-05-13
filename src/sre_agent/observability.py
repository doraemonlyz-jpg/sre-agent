"""
Opt-in export of harness records to a centralized backend.

The L3 ring buffer (`harness.RECORDER`) is in-process. That's fine for
a single replica + interview demo, but a real fleet needs:

  * Retention beyond process restart.
  * Cross-replica aggregation (compute per-prompt-SHA accuracy across
    every region).
  * Alertable timelines (PagerDuty rule on "p99 latency for hypothesis-gen
    > 8s for 5 minutes").

Three modes, picked by env:

  1. `OFF` (default) — no export. Records live only in the ring buffer.

  2. `LANGFUSE` — ship to Langfuse Cloud / self-hosted. Set
        LANGFUSE_PUBLIC_KEY=pk-...
        LANGFUSE_SECRET_KEY=sk-...
        LANGFUSE_HOST=https://cloud.langfuse.com   # optional
     We use Langfuse's official client; if it's not installed we degrade
     to OFF + log a warning rather than crash.

  3. `OTLP` — generic OpenTelemetry. Set
        OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector.team.svc:4318
        OTEL_SERVICE_NAME=sre-agent
     OpenTelemetry tracer is configured at import time; spans are
     emitted from the HarnessCallback path. Same degradation rule.

This module reads each record produced by `HarnessRecorder.record()` via
a subscriber pattern — we don't re-architect the recorder, we just hook
into it.

Production note: the export is best-effort and asynchronous. Failures
are logged and counted but never raised — observability MUST NOT bring
down the system it observes.
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import os
import queue
import threading
from typing import Any

from sre_agent.harness import RECORDER, LLMCallRecord

log = logging.getLogger("sre_agent.observability")


# ──────────────────────────────────────────────────────────────────────────
# Mode detection
# ──────────────────────────────────────────────────────────────────────────


def detect_mode() -> str:
    """Return 'off' | 'langfuse' | 'otlp' based on env."""
    if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
        return "langfuse"
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return "otlp"
    if os.environ.get("SRE_OBSERVABILITY_MODE", "").lower() == "stdout":
        return "stdout"  # debug mode — print every record
    return "off"


# ──────────────────────────────────────────────────────────────────────────
# Background exporter
# ──────────────────────────────────────────────────────────────────────────


class _Exporter:
    """
    A single background thread drains a queue of LLMCallRecords and ships
    them. We use a queue + thread so the agent's hot path never blocks on
    network I/O.
    """

    def __init__(self) -> None:
        self.mode = detect_mode()
        self._queue: queue.Queue[LLMCallRecord] = queue.Queue(maxsize=10_000)
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._failed = 0
        self._sent = 0
        self._dropped = 0
        self._lf_client: Any | None = None

        if self.mode == "off":
            log.info("observability.disabled")
            return

        self._init_backend()
        self._worker = threading.Thread(
            target=self._drain_loop,
            name="sre-observability",
            daemon=True,
        )
        self._worker.start()
        atexit.register(self.flush)

    # ── backend init ─────────────────────────────────────────────────

    def _init_backend(self) -> None:
        if self.mode == "langfuse":
            try:
                from langfuse import Langfuse  # type: ignore[import-not-found]

                self._lf_client = Langfuse(
                    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
                    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
                    host=os.environ.get("LANGFUSE_HOST"),
                )
                log.info("observability.langfuse.ready host=%s",
                         os.environ.get("LANGFUSE_HOST", "default"))
            except Exception as e:
                log.warning("observability.langfuse.unavailable error=%s — degrading to OFF", e)
                self.mode = "off"

        elif self.mode == "otlp":
            try:
                from opentelemetry import trace  # type: ignore[import-not-found]
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-not-found]
                    OTLPSpanExporter,
                )
                from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
                from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
                from opentelemetry.sdk.trace.export import (
                    BatchSpanProcessor,  # type: ignore[import-not-found]
                )

                resource = Resource.create(
                    {"service.name": os.environ.get("OTEL_SERVICE_NAME", "sre-agent")}
                )
                provider = TracerProvider(resource=resource)
                provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
                trace.set_tracer_provider(provider)
                self._otel = trace.get_tracer("sre-agent")
                log.info(
                    "observability.otlp.ready endpoint=%s",
                    os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
                )
            except Exception as e:
                log.warning("observability.otlp.unavailable error=%s — degrading to OFF", e)
                self.mode = "off"

        elif self.mode == "stdout":
            log.info("observability.stdout.ready")

    # ── enqueue (hot path) ───────────────────────────────────────────

    def enqueue(self, rec: LLMCallRecord) -> None:
        """Non-blocking — drops + counts on overflow rather than backpressuring the agent."""
        if self.mode == "off":
            return
        try:
            self._queue.put_nowait(rec)
        except queue.Full:
            self._dropped += 1

    # ── drain loop ───────────────────────────────────────────────────

    def _drain_loop(self) -> None:
        while not self._stop.is_set():
            try:
                rec = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._ship(rec)
                self._sent += 1
            except Exception as e:
                self._failed += 1
                # Log at most one per 100 to avoid drowning the log on
                # a misconfigured backend.
                if self._failed % 100 == 1:
                    log.warning("observability.ship_failed n=%d last_error=%s",
                                self._failed, e)

    def _ship(self, rec: LLMCallRecord) -> None:
        if self.mode == "langfuse":
            self._ship_langfuse(rec)
        elif self.mode == "otlp":
            self._ship_otlp(rec)
        elif self.mode == "stdout":
            print(f"[observability] {rec.to_json()}")

    def _ship_langfuse(self, rec: LLMCallRecord) -> None:
        if rec.kind != "llm_call" or self._lf_client is None:
            return
        # Langfuse `generation` is the closest fit to "one LLM call".
        self._lf_client.generation(
            name=rec.agent,
            model=rec.model,
            metadata={
                "incident_id": rec.incident_id,
                "prompt_sha": rec.prompt_sha,
                "status": rec.status,
                "role": rec.role,
            },
            input=None,  # full prompts are intentionally not exported
            output=None,  # — keep PII / cost low
            usage={
                "input": rec.input_tokens or 0,
                "output": rec.output_tokens or 0,
            },
            level="ERROR" if rec.status == "error" else "DEFAULT",
            status_message=rec.error,
        )

    def _ship_otlp(self, rec: LLMCallRecord) -> None:
        tracer = getattr(self, "_otel", None)
        if tracer is None:
            return
        with tracer.start_as_current_span(
            name=f"llm.{rec.agent}",
            attributes={
                "llm.model": rec.model or "",
                "llm.role": rec.role or "",
                "llm.prompt_sha": rec.prompt_sha or "",
                "llm.status": rec.status,
                "llm.input_tokens": rec.input_tokens or 0,
                "llm.output_tokens": rec.output_tokens or 0,
                "sre.incident_id": rec.incident_id or "",
            },
        ) as span:
            if rec.latency_ms is not None:
                span.set_attribute("llm.latency_ms", rec.latency_ms)
            if rec.error:
                span.record_exception(Exception(rec.error))

    # ── lifecycle ────────────────────────────────────────────────────

    def flush(self) -> None:
        """Block briefly to drain pending records on shutdown."""
        if self.mode == "off":
            return
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=2.0)
        if self.mode == "langfuse" and self._lf_client is not None:
            with contextlib.suppress(Exception):
                self._lf_client.flush()

    def stats(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "sent": self._sent,
            "failed": self._failed,
            "dropped": self._dropped,
            "queue_depth": self._queue.qsize(),
        }


# Process-wide singleton initialized at import; pluggable for tests.
EXPORTER = _Exporter()


# ──────────────────────────────────────────────────────────────────────────
# Subscriber: tap RECORDER.record() without changing harness.py
# ──────────────────────────────────────────────────────────────────────────


def _wrap_recorder() -> None:
    """
    Wrap `RECORDER.record` so every record gets enqueued for export.
    Idempotent: re-wrapping is a no-op (we check the marker attribute).
    """
    if getattr(RECORDER.record, "_export_wrapped", False):
        return
    original = RECORDER.record

    def wrapped(rec: LLMCallRecord) -> None:
        original(rec)
        # Never crash the recording path — observability MUST NOT bring
        # down the system it observes.
        with contextlib.suppress(Exception):
            EXPORTER.enqueue(rec)

    wrapped._export_wrapped = True  # type: ignore[attr-defined]
    RECORDER.record = wrapped  # type: ignore[method-assign]


_wrap_recorder()
