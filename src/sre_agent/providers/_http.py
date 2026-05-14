"""
sre_agent.providers._http -- shared HTTP plumbing for real providers.

Why this exists
---------------
The real PrometheusProvider and LokiProvider both call HTTP backends
that exhibit textbook transient-failure shapes:

  * 502 / 503 / 504 from a load-balancer evicting a backend
  * Connection reset on a long-running query
  * 429 from a rate-limiter on a noisy neighbour

A single retry with exponential backoff turns 90% of these from "the
incident pipeline returned ERROR" into "a 200ms tax on one node".

Also centralises:

  * **Authentication** -- bearer token, basic auth, or none, controlled
    by env vars so the same code paths cover dev (no auth) and prod
    (everything authed).
  * **Self-metrics** -- each provider invocation bumps a Prometheus
    counter / histogram so ops can dashboard the agent's own back-end
    health, not just the LLM side.

Both providers wrap their `httpx.Client` in a `RetryingClient` made by
`make_retrying_client(...)`. Tests inject their own client for offline
testing -- this module never assumes `make_retrying_client` is the
only path.
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any

import httpx

log = logging.getLogger("sre_agent.providers.http")


# ──────────────────────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────────────────────


def _build_auth_header(prefix: str) -> dict[str, str]:
    """
    Build an Authorization header dict from env. `prefix` is the
    provider-specific prefix, e.g. ``PROMETHEUS`` for
    ``PROMETHEUS_BEARER_TOKEN`` / ``PROMETHEUS_BASIC_AUTH_USER``.

    Returns an empty dict when no auth is configured -- callers can
    safely splat it into headers.
    """
    bearer = os.environ.get(f"{prefix}_BEARER_TOKEN", "").strip()
    if bearer:
        return {"Authorization": f"Bearer {bearer}"}

    user = os.environ.get(f"{prefix}_BASIC_AUTH_USER", "").strip()
    pw = os.environ.get(f"{prefix}_BASIC_AUTH_PASSWORD", "").strip()
    if user and pw:
        import base64
        token = base64.b64encode(f"{user}:{pw}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    return {}


# ──────────────────────────────────────────────────────────────────────────
# Retry policy
# ──────────────────────────────────────────────────────────────────────────


_RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_BASE_DELAY_S = 0.2
_DEFAULT_MAX_DELAY_S = 5.0


class RetryingClient:
    """
    Thin wrapper around `httpx.Client` that retries idempotent verbs on
    transient errors with exponential backoff + jitter.

    The wrapper proxies `.get()` / `.post()` / `.close()` / context
    management. We deliberately do NOT subclass `httpx.Client` because
    httpx's internal hooks aren't part of its public API and we don't
    want to chase them across versions.

    Self-metrics: `sre_provider_request_total{provider,outcome}` and
    `sre_provider_request_latency_seconds{provider}`.
    """

    def __init__(
        self,
        inner: httpx.Client,
        *,
        provider_name: str,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
        base_delay_s: float = _DEFAULT_BASE_DELAY_S,
        max_delay_s: float = _DEFAULT_MAX_DELAY_S,
    ) -> None:
        self._inner = inner
        self.provider_name = provider_name
        self.max_attempts = max(1, int(max_attempts))
        self.base_delay_s = base_delay_s
        self.max_delay_s = max_delay_s

    # ── public surface ──────────────────────────────────────────────

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._with_retry("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._with_retry("POST", url, **kwargs)

    def close(self) -> None:
        self._inner.close()

    def __enter__(self) -> "RetryingClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── implementation ──────────────────────────────────────────────

    def _with_retry(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_exc: BaseException | None = None
        last_resp: httpx.Response | None = None
        for attempt in range(1, self.max_attempts + 1):
            t0 = time.perf_counter()
            outcome = "ok"
            try:
                if method == "GET":
                    resp = self._inner.get(url, **kwargs)
                else:
                    resp = self._inner.post(url, **kwargs)

                if resp.status_code in _RETRY_STATUS_CODES and attempt < self.max_attempts:
                    last_resp = resp
                    outcome = f"retry_{resp.status_code}"
                    self._record(outcome, time.perf_counter() - t0)
                    self._sleep_backoff(attempt)
                    continue
                # Either success or terminal non-retryable status -- return as-is.
                outcome = "ok" if 200 <= resp.status_code < 300 else f"http_{resp.status_code}"
                self._record(outcome, time.perf_counter() - t0)
                return resp
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
                last_exc = e
                outcome = type(e).__name__.lower()
                self._record(outcome, time.perf_counter() - t0)
                if attempt < self.max_attempts:
                    self._sleep_backoff(attempt)
                    continue
                raise
            except Exception as e:
                last_exc = e
                self._record(f"error.{type(e).__name__.lower()}", time.perf_counter() - t0)
                raise

        # All attempts retried. Return the last response if we have one,
        # else re-raise the last exception. (We can't reach here without
        # one of those being set, but be defensive.)
        if last_resp is not None:
            return last_resp
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(
            f"{self.provider_name}: retry loop exhausted with neither response nor exception"
        )

    def _sleep_backoff(self, attempt: int) -> None:
        # Exp backoff with full jitter -- standard AWS-style: random in [0, ceil)
        # rather than fixed multipliers. Avoids retry storms.
        ceiling = min(self.max_delay_s, self.base_delay_s * (2 ** (attempt - 1)))
        delay = random.uniform(0, ceiling)
        log.debug(
            "%s.retry attempt=%d sleeping=%.2fs", self.provider_name, attempt, delay,
        )
        time.sleep(delay)

    def _record(self, outcome: str, latency_s: float) -> None:
        try:
            from sre_agent import metrics as _m
            _m.PROVIDER_REQUESTS_TOTAL.labels(
                provider=self.provider_name, outcome=outcome,
            ).inc()
            _m.PROVIDER_REQUEST_LATENCY.labels(
                provider=self.provider_name,
            ).observe(latency_s)
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────
# Builder
# ──────────────────────────────────────────────────────────────────────────


def make_retrying_client(
    *,
    base_url: str,
    timeout_s: float,
    provider_name: str,
    auth_env_prefix: str,
    extra_headers: dict[str, str] | None = None,
) -> RetryingClient:
    """
    Construct a `RetryingClient` wired with auth headers from env and
    sensible defaults. Used by both PrometheusProvider and LokiProvider
    -- and by any future real provider (e.g. OpenSearch, Tempo).
    """
    headers = {**(extra_headers or {}), **_build_auth_header(auth_env_prefix)}
    inner = httpx.Client(base_url=base_url, timeout=timeout_s, headers=headers)
    return RetryingClient(inner, provider_name=provider_name)


# ──────────────────────────────────────────────────────────────────────────
# Health probe
# ──────────────────────────────────────────────────────────────────────────


def probe_health(
    client: RetryingClient | httpx.Client,
    *,
    path: str,
    timeout_s: float = 2.0,
    success_status: int = 200,
) -> dict[str, Any]:
    """
    Standard "tap the backend's health endpoint, time it, return a
    one-shot dict" used by readiness probes.

    Returns ``{"ok": bool, "status_code": int | None, "latency_ms": float, "error": str | None}``.

    Never raises -- the readiness probe should report `ok=False` on
    error, not crash the dashboard.
    """
    t0 = time.perf_counter()
    try:
        # RetryingClient's `get` doesn't accept a per-call timeout override;
        # we use the underlying client directly for health checks so
        # they aren't subject to the retry loop (a hung backend should
        # show as unhealthy fast, not after 3 retries).
        inner = getattr(client, "_inner", client)
        resp = inner.get(path, timeout=timeout_s)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        ok = resp.status_code == success_status
        return {
            "ok": ok,
            "status_code": resp.status_code,
            "latency_ms": round(latency_ms, 1),
            "error": None if ok else f"unexpected status {resp.status_code}",
        }
    except Exception as e:
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
            "error": f"{type(e).__name__}: {str(e)[:120]}",
        }
