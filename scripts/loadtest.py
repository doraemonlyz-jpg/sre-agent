"""
Quick-and-dirty load test for the dashboard.

Why we have this in-tree:

  * Locust / k6 are great but adding them as a dev dep just to send
    JSON POSTs is overkill. This script is ~100 lines of stdlib +
    `httpx` (already a dep) and emits a sensible summary.
  * Smoke covers correctness. Load covers *bounded* throughput — i.e.
    "can the dashboard serve N rps without 5xx?"
  * The bounded-worker-pool + the rate-limiter together cap LLM cost.
    This script verifies that cap is honored (excess requests get 429,
    not 5xx).

Usage:

    python scripts/loadtest.py \\
        --base http://localhost:5050 \\
        --rps 20 --duration 30 \\
        --service checkout-api

    # With auth:
    AUTH_TOKEN=tok-xyz python scripts/loadtest.py --rps 5 --duration 10

Output is a compact table at the end with per-status counts, p50/p95/p99
latencies, and rate-limit yield (429 count / total).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time
from dataclasses import dataclass, field

import httpx


@dataclass
class _Stat:
    counts: dict[int, int] = field(default_factory=dict)
    latencies_ms: list[float] = field(default_factory=list)
    errors: int = 0

    def record(self, status: int, latency_ms: float) -> None:
        self.counts[status] = self.counts.get(status, 0) + 1
        self.latencies_ms.append(latency_ms)

    def record_error(self) -> None:
        self.errors += 1

    def pct(self, p: float) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_lat = sorted(self.latencies_ms)
        idx = max(0, min(len(sorted_lat) - 1, int(len(sorted_lat) * p)))
        return sorted_lat[idx]

    def summary(self, total_seconds: float) -> str:
        total = sum(self.counts.values()) + self.errors
        rps = total / total_seconds if total_seconds > 0 else 0.0
        lines = [
            f"total requests : {total}",
            f"duration       : {total_seconds:.1f}s",
            f"throughput     : {rps:.1f} rps",
            f"errors         : {self.errors}",
            "status mix     : "
            + ", ".join(f"{k}={v}" for k, v in sorted(self.counts.items())),
        ]
        if self.latencies_ms:
            lines += [
                f"latency p50    : {self.pct(0.5):.0f} ms",
                f"latency p95    : {self.pct(0.95):.0f} ms",
                f"latency p99    : {self.pct(0.99):.0f} ms",
                f"latency max    : {max(self.latencies_ms):.0f} ms",
                f"latency mean   : {statistics.mean(self.latencies_ms):.0f} ms",
            ]
        return "\n".join(lines)


async def _fire_one(
    client: httpx.AsyncClient, url: str, payload: dict, stat: _Stat
) -> None:
    started = time.perf_counter()
    try:
        r = await client.post(url, json=payload, timeout=10.0)
        elapsed_ms = (time.perf_counter() - started) * 1000
        stat.record(r.status_code, elapsed_ms)
    except Exception:
        stat.record_error()


async def _run(args: argparse.Namespace) -> None:
    interval_s = 1.0 / args.rps if args.rps > 0 else 0.0
    headers = {}
    if os.environ.get("AUTH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["AUTH_TOKEN"]

    stat = _Stat()
    payload = {
        "service": args.service,
        "severity": args.severity,
        "description": args.description,
    }
    url = f"{args.base.rstrip('/')}/api/incidents/fire"

    started = time.perf_counter()
    end = started + args.duration

    async with httpx.AsyncClient(headers=headers) as client:
        tasks: list[asyncio.Task] = []
        while time.perf_counter() < end:
            tasks.append(asyncio.create_task(_fire_one(client, url, payload, stat)))
            await asyncio.sleep(interval_s)
        await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - started

    print()
    print("─── loadtest summary ─────────────────────────────────────")
    print(stat.summary(elapsed))
    print("──────────────────────────────────────────────────────────")

    # Health check: anything 5xx is a real failure. 429s are EXPECTED if
    # rate limit is on — they're the system protecting itself.
    n5xx = sum(v for k, v in stat.counts.items() if 500 <= k < 600)
    if n5xx or stat.errors:
        raise SystemExit(
            f"loadtest FAIL: {n5xx} 5xx responses, {stat.errors} client errors"
        )
    print("loadtest OK (no 5xx)")


def _cli() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", default=os.environ.get("BASE", "http://localhost:5050"))
    p.add_argument("--rps", type=float, default=10.0)
    p.add_argument("--duration", type=float, default=20.0)
    p.add_argument("--service", default="checkout-api")
    p.add_argument("--severity", default="SEV-2")
    p.add_argument(
        "--description",
        default="loadtest: p99 latency anomaly + error rate climb",
    )
    args = p.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    _cli()
