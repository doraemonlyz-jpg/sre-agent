"""
Tests for Slack interactive payload parsing + HMAC verification.

Security-critical: if these tests pass but verification is buggy,
anyone with our public URL can forge oncall feedback.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest

from sre_agent.slack_actions import (
    SlackActionError,
    parse_payload,
    verify_required,
    verify_signature,
)


def _sign(body: bytes, ts: str, secret: str) -> str:
    base = f"v0:{ts}:".encode() + body
    return "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()


class TestVerifySignature:
    def test_valid_signature_accepted(self):
        body = b"hello"
        ts = str(int(time.time()))
        secret = "shhh"
        sig = _sign(body, ts, secret)
        assert verify_signature(body=body, timestamp=ts, signature=sig, secret=secret) is True

    def test_wrong_signature_rejected(self):
        body = b"hello"
        ts = str(int(time.time()))
        secret = "shhh"
        sig = _sign(body, ts, secret)
        # Flip one character
        bad = sig[:-1] + ("a" if sig[-1] != "a" else "b")
        assert verify_signature(body=body, timestamp=ts, signature=bad, secret=secret) is False

    def test_old_timestamp_rejected(self):
        body = b"hello"
        ts = str(int(time.time()) - 600)  # 10 min ago, default max_age 5 min
        secret = "shhh"
        sig = _sign(body, ts, secret)
        assert verify_signature(body=body, timestamp=ts, signature=sig, secret=secret) is False

    def test_missing_secret_rejected(self, monkeypatch):
        monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
        assert verify_signature(body=b"x", timestamp="1", signature="v0=zzz") is False

    def test_non_int_timestamp_rejected(self):
        assert (
            verify_signature(body=b"x", timestamp="not-a-number", signature="v0=zzz", secret="s")
            is False
        )

    def test_modified_body_rejected(self):
        secret = "shhh"
        ts = str(int(time.time()))
        sig = _sign(b"original", ts, secret)
        assert (
            verify_signature(body=b"tampered", timestamp=ts, signature=sig, secret=secret)
            is False
        )


# ──────────────────────────────────────────────────────────────────────────
# parse_payload — happy path + every malformed-input branch
# ──────────────────────────────────────────────────────────────────────────


def _slack_form(action_id: str, value: str, **user_kw) -> dict:
    payload = {
        "actions": [{"action_id": action_id, "value": value}],
        "user": user_kw or {"username": "alice", "id": "U1"},
    }
    return {"payload": json.dumps(payload)}


class TestParsePayload:
    def test_thumbs_up(self):
        out = parse_payload(_slack_form("sre_feedback_up", "inc-1"))
        assert out.verdict == "thumbs_up"
        assert out.incident_id == "inc-1"
        assert out.user_name == "alice"

    def test_thumbs_down(self):
        out = parse_payload(_slack_form("sre_feedback_down", "inc-2"))
        assert out.verdict == "thumbs_down"
        assert out.tags == []

    def test_false_positive_tags_attached(self):
        out = parse_payload(_slack_form("sre_mark_falsepos", "inc-3"))
        assert out.verdict == "incorrect"
        assert "false-positive" in out.tags

    def test_unknown_action_id_rejected(self):
        with pytest.raises(SlackActionError, match="unknown action_id"):
            parse_payload(_slack_form("sre_drop_database", "inc-1"))

    def test_missing_value_rejected(self):
        with pytest.raises(SlackActionError, match="no incident_id"):
            parse_payload(_slack_form("sre_feedback_up", ""))

    def test_no_payload_field(self):
        with pytest.raises(SlackActionError, match="missing 'payload'"):
            parse_payload({})

    def test_malformed_json(self):
        with pytest.raises(SlackActionError, match="not JSON"):
            parse_payload({"payload": "{not-json"})

    def test_no_actions(self):
        with pytest.raises(SlackActionError, match="no actions"):
            parse_payload({"payload": json.dumps({"actions": []})})


class TestVerifyRequiredEnv:
    def test_default_off(self, monkeypatch):
        monkeypatch.delenv("SRE_SLACK_VERIFY_REQUIRED", raising=False)
        assert verify_required() is False

    def test_on_when_set(self, monkeypatch):
        monkeypatch.setenv("SRE_SLACK_VERIFY_REQUIRED", "1")
        assert verify_required() is True
