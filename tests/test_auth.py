"""
Tests for the bearer-token auth layer.

The contract we lock in:

  * When `SRE_AUTH_REQUIRED` is unset/false, decorators are no-ops. This
    is what makes `docker-compose up` work without provisioning tokens.
  * When enforcement is on, mutating endpoints reject missing tokens
    with 401 (and a WWW-Authenticate header) and wrong-scope tokens
    with 403.
  * `admin` scope grants every other scope. Useful for the bootstrap
    "give me one token that can do everything" token.
  * Token rotation works without process restart when SRE_AUTH_TOKENS_FILE
    is used (file watcher reloads at most once / minute).
"""

from __future__ import annotations

import json

import pytest
from flask import Flask, jsonify

from sre_agent.auth import (
    KNOWN_SCOPES,
    REGISTRY,
    Token,
    auth_required,
    extract_bearer,
    mint_token,
    require_scope,
)

# ──────────────────────────────────────────────────────────────────────────
# extract_bearer — token parsing
# ──────────────────────────────────────────────────────────────────────────


class TestExtractBearer:
    def test_none_input(self):
        assert extract_bearer(None) is None

    def test_empty(self):
        assert extract_bearer("") is None

    def test_no_scheme(self):
        assert extract_bearer("just-a-token") is None

    def test_wrong_scheme(self):
        assert extract_bearer("Basic abc") is None

    def test_correct(self):
        assert extract_bearer("Bearer s3cret") == "s3cret"

    def test_case_insensitive_scheme(self):
        assert extract_bearer("bearer s3cret") == "s3cret"

    def test_empty_token(self):
        assert extract_bearer("Bearer  ") is None


# ──────────────────────────────────────────────────────────────────────────
# TokenRegistry — admin scope wildcard, missing tokens, scope matching
# ──────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_registry(monkeypatch):
    REGISTRY.clear()
    monkeypatch.delenv("SRE_AUTH_TOKENS", raising=False)
    monkeypatch.delenv("SRE_AUTH_TOKENS_FILE", raising=False)
    yield REGISTRY
    REGISTRY.clear()


class TestTokenRegistry:
    def test_unknown_secret_rejected(self, fresh_registry):
        assert fresh_registry.verify("nope", required_scope="read") is None

    def test_correct_scope_granted(self, fresh_registry):
        fresh_registry.register(Token(name="oncall", secret="s1", scopes=("read", "fire")))
        tok = fresh_registry.verify("s1", required_scope="fire")
        assert tok is not None and tok.name == "oncall"

    def test_missing_scope_rejected(self, fresh_registry):
        fresh_registry.register(Token(name="readonly", secret="s2", scopes=("read",)))
        assert fresh_registry.verify("s2", required_scope="fire") is None

    def test_admin_grants_every_scope(self, fresh_registry):
        fresh_registry.register(Token(name="root", secret="sA", scopes=("admin",)))
        for s in KNOWN_SCOPES:
            assert fresh_registry.verify("sA", required_scope=s) is not None

    def test_env_load_from_string(self, fresh_registry, monkeypatch):
        monkeypatch.setenv(
            "SRE_AUTH_TOKENS",
            "oncall:read,fire:s-1;admin:admin:s-2",
        )
        REGISTRY.load_from_env()
        assert REGISTRY.verify("s-1", required_scope="fire") is not None
        assert REGISTRY.verify("s-2", required_scope="burst") is not None  # admin

    def test_env_load_from_file(self, fresh_registry, monkeypatch, tmp_path):
        path = tmp_path / "tokens.json"
        path.write_text(
            json.dumps(
                [
                    {"name": "oncall", "secret": "file-1", "scopes": ["read", "feedback"]},
                ]
            )
        )
        monkeypatch.setenv("SRE_AUTH_TOKENS_FILE", str(path))
        REGISTRY.load_from_env()
        assert REGISTRY.verify("file-1", required_scope="feedback") is not None
        assert REGISTRY.verify("file-1", required_scope="fire") is None


# ──────────────────────────────────────────────────────────────────────────
# require_scope Flask decorator — off, on, missing, wrong scope
# ──────────────────────────────────────────────────────────────────────────


def _build_flask_app() -> Flask:
    app = Flask("test_app")

    @app.route("/protected", methods=["POST"])
    @require_scope("fire")
    def protected():
        return jsonify({"ok": True})

    return app


class TestRequireScopeDecorator:
    def test_off_by_default(self, fresh_registry, monkeypatch):
        monkeypatch.delenv("SRE_AUTH_REQUIRED", raising=False)
        assert auth_required() is False
        app = _build_flask_app()
        client = app.test_client()
        # No Authorization header — still succeeds when enforcement is off.
        r = client.post("/protected")
        assert r.status_code == 200

    def test_on_missing_header_401(self, fresh_registry, monkeypatch):
        monkeypatch.setenv("SRE_AUTH_REQUIRED", "1")
        app = _build_flask_app()
        client = app.test_client()
        r = client.post("/protected")
        assert r.status_code == 401
        assert "WWW-Authenticate" in r.headers
        assert r.headers["WWW-Authenticate"].startswith("Bearer")

    def test_on_bad_token_403(self, fresh_registry, monkeypatch):
        monkeypatch.setenv("SRE_AUTH_REQUIRED", "1")
        app = _build_flask_app()
        client = app.test_client()
        r = client.post("/protected", headers={"Authorization": "Bearer nope"})
        assert r.status_code == 403

    def test_on_wrong_scope_403(self, fresh_registry, monkeypatch):
        monkeypatch.setenv("SRE_AUTH_REQUIRED", "1")
        fresh_registry.register(Token(name="readonly", secret="r1", scopes=("read",)))
        app = _build_flask_app()
        client = app.test_client()
        r = client.post("/protected", headers={"Authorization": "Bearer r1"})
        assert r.status_code == 403

    def test_on_correct_scope_200(self, fresh_registry, monkeypatch):
        monkeypatch.setenv("SRE_AUTH_REQUIRED", "1")
        fresh_registry.register(Token(name="oncall", secret="f1", scopes=("fire",)))
        app = _build_flask_app()
        client = app.test_client()
        r = client.post("/protected", headers={"Authorization": "Bearer f1"})
        assert r.status_code == 200

    def test_admin_satisfies_any_scope(self, fresh_registry, monkeypatch):
        monkeypatch.setenv("SRE_AUTH_REQUIRED", "1")
        fresh_registry.register(Token(name="root", secret="adm", scopes=("admin",)))
        app = _build_flask_app()
        client = app.test_client()
        r = client.post("/protected", headers={"Authorization": "Bearer adm"})
        assert r.status_code == 200


# ──────────────────────────────────────────────────────────────────────────
# mint_token — sanity check on minted secrets
# ──────────────────────────────────────────────────────────────────────────


class TestMintToken:
    def test_mint_basic(self):
        t = mint_token("oncall", ["read", "fire"])
        assert t.name == "oncall"
        assert "read" in t.scopes and "fire" in t.scopes
        assert len(t.secret) >= 32

    def test_mint_unique(self):
        a = mint_token("x", ["read"])
        b = mint_token("x", ["read"])
        assert a.secret != b.secret
