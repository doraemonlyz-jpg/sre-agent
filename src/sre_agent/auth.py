"""
Bearer-token auth for the dashboard's mutating endpoints.

Why we need this for prod:

  * Anyone on the network can POST /api/incidents/fire today — a janky
    web crawler firing 1k bogus incidents would (a) burn LLM dollars,
    (b) pollute the harness ring buffer, and (c) poison the response
    cache for ~5 minutes per misfire.
  * We need a second "kill switch" beyond network ACLs — bearer tokens
    that we can rotate without a redeploy.

Design choices:

  * In-process token registry. Tokens live in `SRE_AUTH_TOKENS` (env)
    or `SRE_AUTH_TOKENS_FILE` (path to a json file). For real prod
    this would be a JWT verifier reading a JWKS from your IdP — same
    `verify_token()` interface, just a different backend.
  * **Scopes**, not roles. The dashboard has 4 capabilities:
      - `read`        : list / get incidents
      - `fire`        : create incidents
      - `burst`       : POST /api/incidents/burst   (could be `fire` only,
                        but bursts are dangerous so they get their own)
      - `feedback`    : POST /api/incidents/<id>/feedback
      - `admin`       : everything, including invalidating cache / dumping
                        records
  * Opt-in. `SRE_AUTH_REQUIRED=1` enables enforcement. Default OFF so
    `docker-compose up` still works for the demo.
  * Failure mode is **explicit 401 with WWW-Authenticate header** so a
    browser would actually prompt — we never silently fail open.

The decorator below is intentionally Flask-flavored; if we ever
swap to FastAPI, only the decorator changes.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from threading import RLock

log = logging.getLogger("sre_agent.auth")


# Scopes we recognize. Order matters only for human readability in error
# messages — semantically every scope is a flat label.
KNOWN_SCOPES = ("read", "fire", "burst", "feedback", "admin")


@dataclass
class Token:
    """One issued credential."""

    name: str                 # human label, e.g. "oncall-prod"
    secret: str               # the bearer value, opaque
    scopes: tuple[str, ...]   # which capabilities this token can use
    issued_at: float = field(default_factory=time.time)
    note: str = ""            # free-form (which team owns it, etc.)


@dataclass
class TokenRegistry:
    """Process-wide registry. Reload from file at most once per minute."""

    _lock: RLock = field(default_factory=RLock)
    _by_secret: dict[str, Token] = field(default_factory=dict)
    _source_path: Path | None = None
    _last_load: float = 0.0
    _ttl: float = 60.0

    # ── loading ─────────────────────────────────────────────────────

    def load_from_env(self) -> None:
        """
        Load tokens from `SRE_AUTH_TOKENS` (semicolon list of
        `name:scope1,scope2:secret`) or `SRE_AUTH_TOKENS_FILE`.

        Examples:
            SRE_AUTH_TOKENS="oncall:read,fire,feedback:s3cret-A;admin:admin:s3cret-B"
            SRE_AUTH_TOKENS_FILE=/etc/sre-agent/tokens.json

        File format:
            [{"name": "oncall", "scopes": ["read","fire"], "secret": "..."}]
        """
        with self._lock:
            self._by_secret.clear()
            raw = os.environ.get("SRE_AUTH_TOKENS")
            path = os.environ.get("SRE_AUTH_TOKENS_FILE")
            if path:
                self._source_path = Path(path).expanduser()
                if self._source_path.is_file():
                    try:
                        for t in json.loads(self._source_path.read_text("utf-8")):
                            self._register(
                                Token(
                                    name=t["name"],
                                    secret=t["secret"],
                                    scopes=tuple(t.get("scopes", ["read"])),
                                    note=t.get("note", ""),
                                )
                            )
                    except Exception:
                        log.exception("auth.token_file_parse_failed path=%s", self._source_path)
            elif raw:
                for entry in raw.split(";"):
                    entry = entry.strip()
                    if not entry:
                        continue
                    parts = entry.split(":")
                    if len(parts) != 3:
                        log.warning("auth.token_entry_malformed %s", entry)
                        continue
                    name, scopes_csv, secret = parts
                    self._register(
                        Token(
                            name=name.strip(),
                            secret=secret.strip(),
                            scopes=tuple(s.strip() for s in scopes_csv.split(",") if s.strip()),
                        )
                    )
            self._last_load = time.time()

    def _maybe_reload(self) -> None:
        """File-based registries get reloaded lazily so token rotation
        doesn't require a restart. Skips when env-only mode OR when the
        token-source env var is no longer set (e.g. between tests)."""
        if not self._source_path:
            return
        # If the env that pointed us at the source file is GONE, the
        # previous _source_path is stale — don't reload over it, or we'd
        # wipe out tokens registered programmatically (e.g. by tests).
        if not os.environ.get("SRE_AUTH_TOKENS_FILE"):
            return
        if time.time() - self._last_load < self._ttl:
            return
        try:
            self.load_from_env()
        except Exception:
            log.exception("auth.reload_failed")

    def _register(self, token: Token) -> None:
        unknown = [s for s in token.scopes if s not in KNOWN_SCOPES]
        if unknown:
            log.warning("auth.token_unknown_scopes name=%s scopes=%s", token.name, unknown)
        self._by_secret[token.secret] = token

    # ── verification ───────────────────────────────────────────────

    def verify(self, secret: str, *, required_scope: str) -> Token | None:
        """Return the token if `secret` exists and has `required_scope`."""
        self._maybe_reload()
        with self._lock:
            t = self._by_secret.get(secret)
        if t is None:
            return None
        if "admin" in t.scopes or required_scope in t.scopes:
            return t
        return None

    def register(self, token: Token) -> None:
        """Test hook / programmatic registration."""
        with self._lock:
            self._register(token)

    def clear(self) -> None:
        """Test hook. Resets every piece of state — tokens, source path,
        last-load timestamp — so a subsequent `register()` cannot be
        clobbered by a late `_maybe_reload()` from a previous test's
        env vars."""
        with self._lock:
            self._by_secret.clear()
            self._source_path = None
            self._last_load = 0.0

    def list_tokens(self) -> list[dict]:
        """For /api/auth/me debug endpoint. Never returns secrets."""
        with self._lock:
            return [
                {"name": t.name, "scopes": list(t.scopes), "note": t.note}
                for t in self._by_secret.values()
            ]


REGISTRY = TokenRegistry()
REGISTRY.load_from_env()


# ──────────────────────────────────────────────────────────────────────────
# Flask decorator
# ──────────────────────────────────────────────────────────────────────────


def auth_required() -> bool:
    """Master switch. Off by default so the demo doesn't break."""
    val = os.environ.get("SRE_AUTH_REQUIRED", "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def extract_bearer(authorization_header: str | None) -> str | None:
    if not authorization_header:
        return None
    parts = authorization_header.split(None, 1)
    if len(parts) != 2:
        return None
    scheme, value = parts
    if scheme.lower() != "bearer":
        return None
    return value.strip() or None


def require_scope(scope: str) -> Callable:
    """
    Flask decorator. Skips when SRE_AUTH_REQUIRED is off — so unit tests
    and demo runs don't need to plumb tokens through.
    """
    if scope not in KNOWN_SCOPES:
        raise ValueError(f"unknown scope: {scope}")

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not auth_required():
                return fn(*args, **kwargs)
            from flask import jsonify, request

            token_str = extract_bearer(request.headers.get("Authorization"))
            if not token_str:
                resp = jsonify(
                    {"error": "missing or malformed Authorization header"}
                )
                resp.status_code = 401
                resp.headers["WWW-Authenticate"] = 'Bearer realm="sre-agent"'
                return resp
            tok = REGISTRY.verify(token_str, required_scope=scope)
            if tok is None:
                resp = jsonify(
                    {"error": f"token rejected or missing scope '{scope}'"}
                )
                resp.status_code = 403
                return resp
            # Stash the resolved token on flask.g for handlers that want it
            from flask import g

            g.auth_token = tok
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# ──────────────────────────────────────────────────────────────────────────
# Token minting helper for CLI / first-time setup
# ──────────────────────────────────────────────────────────────────────────


def mint_token(name: str, scopes: list[str], note: str = "") -> Token:
    """Generate a fresh random token. Caller persists it however they want."""
    secret = secrets.token_urlsafe(32)
    return Token(name=name, secret=secret, scopes=tuple(scopes), note=note)
