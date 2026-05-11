"""
chaos-app — a deliberately-buggy Flask service for the SRE Agent demo.

Endpoints:

    GET  /healthy        always 200 (baseline good behaviour)
    GET  /slow           sleep 100-2000ms then 200
    GET  /crash          5% chance of 500 (background noise)
    GET  /redis-leak     "leaks" a redis connection on every call. After
                         50 calls the pool is "exhausted" and every
                         subsequent call returns 500 with the same
                         ConnectionError our Loki provider matches on.
    POST /admin/reset    reset the leak counter (clean slate for demos)
    GET  /metrics        Prometheus exposition (req count, errors,
                         latency histogram, redis connection gauge)

The app also ships every log line directly to Loki via the push API,
so the demo stack doesn't need promtail / Docker logging drivers. This
is unusual in production (you'd normally collect logs out-of-process)
but keeps the demo to a single Loki container.

Env:
    SERVICE_NAME      default 'chaos-app' — labels metrics + logs
    PORT              default 8000
    LOKI_URL          default 'http://loki:3100' — log push destination
    REDIS_LEAK_LIMIT  default 50 — calls before the pool "exhausts"
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import queue
import random
import threading
import time
from datetime import datetime, timezone

import httpx
from flask import Flask, jsonify
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

SERVICE_NAME = os.environ.get("SERVICE_NAME", "chaos-app")
PORT = int(os.environ.get("PORT", "8000"))
LOKI_URL = os.environ.get("LOKI_URL", "http://loki:3100").rstrip("/")
LEAK_LIMIT = int(os.environ.get("REDIS_LEAK_LIMIT", "50"))


# ──────────────────────────────────────────────────────────────────────────
# Prometheus instrumentation
# ──────────────────────────────────────────────────────────────────────────

# The label name `service` matches the default PrometheusProvider templates.
_LABELS = ["service", "endpoint"]
REQUESTS = Counter(
    "chaos_requests_total", "Total HTTP requests handled", _LABELS,
)
ERRORS = Counter(
    "chaos_errors_total", "HTTP requests that returned 5xx", _LABELS,
)
LATENCY = Histogram(
    "chaos_latency_seconds", "Request latency (seconds)", _LABELS,
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
REDIS_CONNS = Gauge(
    "chaos_redis_connections", "Currently 'leaked' redis connections",
    ["service"],
)


# ──────────────────────────────────────────────────────────────────────────
# Loki log shipper — fire-and-forget background queue
# ──────────────────────────────────────────────────────────────────────────


class LokiShipper:
    """Background thread that batches log lines and pushes to Loki."""

    def __init__(self, base_url: str, batch_size: int = 20, flush_s: float = 1.0) -> None:
        self.base_url = base_url
        self.batch_size = batch_size
        self.flush_s = flush_s
        self.q: queue.Queue[tuple[float, dict[str, str], str]] = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def emit(self, ts_ns: int, labels: dict[str, str], line: str) -> None:
        self.q.put((ts_ns, labels, line))

    def _run(self) -> None:
        with httpx.Client(base_url=self.base_url, timeout=5.0) as client:
            while not self._stop.is_set():
                batch: list[tuple[float, dict[str, str], str]] = []
                try:
                    batch.append(self.q.get(timeout=self.flush_s))
                except queue.Empty:
                    continue
                # Drain whatever else is sitting in the queue.
                while not self.q.empty() and len(batch) < self.batch_size:
                    try:
                        batch.append(self.q.get_nowait())
                    except queue.Empty:
                        break
                self._push(client, batch)

    @staticmethod
    def _push(client: httpx.Client, batch: list[tuple[float, dict[str, str], str]]) -> None:
        # Group by label set so each becomes a Loki stream.
        streams: dict[tuple[tuple[str, str], ...], list[list[str]]] = {}
        for ts_ns, labels, line in batch:
            key = tuple(sorted(labels.items()))
            streams.setdefault(key, []).append([str(ts_ns), line])
        body = {
            "streams": [
                {"stream": dict(k), "values": v}
                for k, v in streams.items()
            ],
        }
        # Demo app — don't crash on logging failures.
        with contextlib.suppress(Exception):
            client.post("/loki/api/v1/push", json=body)


_shipper: LokiShipper | None = None


def _log(level: str, message: str, **fields: object) -> None:
    """Emit a structured log line to stdout + Loki."""
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "service": SERVICE_NAME,
        "message": message,
        **fields,
    }
    line = json.dumps(payload, default=str)
    print(line, flush=True)
    if _shipper:
        _shipper.emit(
            int(time.time_ns()),
            {"service": SERVICE_NAME, "level": level},
            line,
        )


# ──────────────────────────────────────────────────────────────────────────
# The app
# ──────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
_leaked = 0  # mutable global — the "bug" the agent should detect


def _observe(endpoint: str, status: int, started_at: float) -> None:
    REQUESTS.labels(SERVICE_NAME, endpoint).inc()
    if status >= 500:
        ERRORS.labels(SERVICE_NAME, endpoint).inc()
    LATENCY.labels(SERVICE_NAME, endpoint).observe(time.time() - started_at)


@app.route("/healthy", methods=["GET"])
def healthy():
    t0 = time.time()
    try:
        return jsonify({"ok": True, "service": SERVICE_NAME})
    finally:
        _observe("/healthy", 200, t0)


@app.route("/slow", methods=["GET"])
def slow():
    t0 = time.time()
    delay = random.uniform(0.1, 2.0)
    time.sleep(delay)
    _log("info", "slow path served", endpoint="/slow", delay_ms=int(delay * 1000))
    _observe("/slow", 200, t0)
    return jsonify({"ok": True, "delay_ms": int(delay * 1000)})


@app.route("/crash", methods=["GET"])
def crash():
    t0 = time.time()
    if random.random() < 0.05:
        _log("error", "random crash hit", endpoint="/crash")
        _observe("/crash", 500, t0)
        return jsonify({"error": "random crash"}), 500
    _observe("/crash", 200, t0)
    return jsonify({"ok": True})


@app.route("/redis-leak", methods=["GET"])
def redis_leak():
    """
    The signature bug. Every call increments a global counter as if we
    forgot to release a redis connection. After LEAK_LIMIT calls the
    "pool" is exhausted and every subsequent call fails with a
    ConnectionError — the same string Loki provider matches on.
    """
    global _leaked
    t0 = time.time()
    _leaked += 1
    REDIS_CONNS.labels(SERVICE_NAME).set(_leaked)

    if _leaked > LEAK_LIMIT:
        _log(
            "error",
            "redis.exceptions.ConnectionError: Connection refused — pool exhausted",
            endpoint="/redis-leak", leaked=_leaked, limit=LEAK_LIMIT,
        )
        _observe("/redis-leak", 500, t0)
        return jsonify({
            "error": "redis.exceptions.ConnectionError",
            "detail": "Connection refused — pool exhausted",
            "leaked": _leaked,
        }), 500

    _log("info", "redis-leak path served", endpoint="/redis-leak", leaked=_leaked)
    _observe("/redis-leak", 200, t0)
    return jsonify({"ok": True, "leaked": _leaked})


@app.route("/admin/reset", methods=["POST"])
def admin_reset():
    global _leaked
    _leaked = 0
    REDIS_CONNS.labels(SERVICE_NAME).set(0)
    _log("info", "leak counter reset", endpoint="/admin/reset")
    return jsonify({"ok": True, "leaked": 0})


@app.route("/metrics", methods=["GET"])
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# ──────────────────────────────────────────────────────────────────────────
# Boot
# ──────────────────────────────────────────────────────────────────────────


def _boot() -> None:
    global _shipper
    _shipper = LokiShipper(LOKI_URL)
    logging.getLogger("werkzeug").setLevel(logging.ERROR)  # quiet flask access logs
    REDIS_CONNS.labels(SERVICE_NAME).set(0)
    _log("info", "chaos-app starting", port=PORT, leak_limit=LEAK_LIMIT)


_boot()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)
