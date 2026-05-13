"""
Tests for the token-bucket rate limiter.
"""

from __future__ import annotations

import time

import pytest
from flask import Flask, jsonify

from sre_agent.ratelimit import LIMITER, _Bucket, rate_for, require


@pytest.fixture(autouse=True)
def reset_limiter():
    LIMITER.reset()
    yield
    LIMITER.reset()


class TestBucket:
    def test_starts_full(self):
        b = _Bucket(capacity=5, refill_per_sec=1, tokens=5.0)
        for _ in range(5):
            assert b.take() is True
        assert b.take() is False

    def test_refills_over_time(self):
        b = _Bucket(capacity=5, refill_per_sec=10, tokens=0.0)
        time.sleep(0.25)  # ~2.5 tokens refilled
        assert b.take(2) is True  # used 2 of ~2.5
        assert b.take(2) is False  # ~0.5 left

    def test_caps_at_capacity(self):
        b = _Bucket(capacity=3, refill_per_sec=100, tokens=0.0)
        time.sleep(0.1)  # would refill 10 tokens, capped at 3
        for _ in range(3):
            assert b.take() is True
        assert b.take() is False


class TestRateFor:
    def test_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("SRE_RATE_FIRE", raising=False)
        rate, cap = rate_for("fire")
        assert (rate, cap) == (10.0, 20.0)

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("SRE_RATE_FIRE", "5:30")
        rate, cap = rate_for("fire")
        assert (rate, cap) == (5.0, 30.0)

    def test_malformed_env_falls_back(self, monkeypatch):
        monkeypatch.setenv("SRE_RATE_FIRE", "nonsense")
        rate, cap = rate_for("fire")
        assert (rate, cap) == (10.0, 20.0)


class TestLimiter:
    def test_disabled_always_allows(self, monkeypatch):
        monkeypatch.setenv("SRE_RATE_LIMIT", "off")
        for _ in range(1000):
            assert LIMITER.check("fire", "ip:1.2.3.4") is True

    def test_per_caller_isolation(self, monkeypatch):
        monkeypatch.setenv("SRE_RATE_LIMIT", "on")
        monkeypatch.setenv("SRE_RATE_FIRE", "1:1")
        LIMITER.reset()
        # Caller A burns its budget
        assert LIMITER.check("fire", "tok:A") is True
        assert LIMITER.check("fire", "tok:A") is False
        # Caller B still has fresh budget
        assert LIMITER.check("fire", "tok:B") is True

    def test_stats_counts(self, monkeypatch):
        monkeypatch.setenv("SRE_RATE_LIMIT", "on")
        monkeypatch.setenv("SRE_RATE_FIRE", "0.1:1")
        LIMITER.reset()
        # First call allowed, second rejected (capacity=1)
        LIMITER.check("fire", "x")
        LIMITER.check("fire", "x")
        s = LIMITER.stats()
        assert s["allowed_total"] == 1
        assert s["rejected_total"] == 1


def _flask_app() -> Flask:
    app = Flask("rl_test")

    @app.route("/fire", methods=["POST"])
    @require("fire")
    def fire():
        return jsonify({"ok": True})

    return app


class TestFlaskDecorator:
    def test_429_when_over_limit(self, monkeypatch):
        monkeypatch.setenv("SRE_RATE_LIMIT", "on")
        monkeypatch.setenv("SRE_RATE_FIRE", "0.01:1")  # 1 burst, very slow refill
        LIMITER.reset()
        app = _flask_app()
        client = app.test_client()

        r1 = client.post("/fire")
        assert r1.status_code == 200

        r2 = client.post("/fire")
        assert r2.status_code == 429
        assert r2.headers.get("Retry-After") == "1"
        body = r2.get_json()
        assert body["error"] == "rate limit exceeded"

    def test_disabled_skips_check(self, monkeypatch):
        monkeypatch.setenv("SRE_RATE_LIMIT", "off")
        app = _flask_app()
        client = app.test_client()
        for _ in range(50):
            assert client.post("/fire").status_code == 200
