"""
End-to-end integration smoke for the L5 surface.

This boots the real Flask app (in-process), points its state at a tmp
dir, fires an incident through the FULL pipeline, and verifies:

  * Auth gates work (401 / 403 paths) when enforcement is on.
  * Rate limit returns 429 when exceeded.
  * Feedback can be submitted and read back.
  * Slack-action endpoint converts a Slack payload into a feedback record.
  * Readiness probe returns ok=true and includes the deep checks.
  * /api/auth/me reports enforced=true and authenticated=true with a
    valid token.

We mock `_run_pipeline` to a fast synchronous diagnose, so we don't
need a live LLM — but the routing / persistence / auth code is the
REAL production code.
"""

from __future__ import annotations

import importlib
import json

import pytest


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    """Boot the Flask app in isolation. Each test gets its own state."""
    # Point all on-disk state at the test tmp dir so we don't clobber
    # the developer's ~/.sre-agent.
    monkeypatch.setenv("SRE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("SRE_FEEDBACK_DIR", str(tmp_path / "feedback"))
    monkeypatch.setenv("SRE_CHECKPOINTER", "memory")
    monkeypatch.setenv("SRE_AUTH_REQUIRED", "0")  # default off; specific tests flip on
    monkeypatch.setenv("SRE_RATE_LIMIT", "off")   # ditto

    # Reset cross-process singletons so we don't inherit state from
    # tests that ran earlier in the same pytest session.
    from sre_agent.auth import REGISTRY as AUTH_REGISTRY
    from sre_agent.cache import CACHE as INCIDENT_CACHE
    from sre_agent.feedback import STORE as FB_STORE
    from sre_agent.ratelimit import LIMITER as RATE_LIMITER

    AUTH_REGISTRY.clear()
    RATE_LIMITER.reset()
    INCIDENT_CACHE.reset()
    FB_STORE.reset()

    import dashboard.app as app_module
    importlib.reload(app_module)

    # Replace the synchronous pipeline runner with a fast stub. The
    # auth/rate-limit/feedback path doesn't care about LLM accuracy.
    def fast_pipeline(incident_id, alert, *args, **kwargs):
        now = app_module._now_ms()
        with app_module.INCIDENTS_LOCK:
            inc = app_module.INCIDENTS.get(incident_id)
            if inc is None:
                return
            inc["phase"] = "diagnosed"
            inc["diagnosed_at"] = now
            inc["diagnosis_ms"] = 50
            inc["hypothesis"] = {"top": "fake", "confidence": 0.8}
            inc["remediation"] = [{"command": "echo ok", "risk": "LOW", "why": "test"}]
            inc["events"].append(
                {"ts": now, "agent": "test-stub", "action": "diagnosed", "detail": "stubbed"}
            )

    monkeypatch.setattr(app_module, "_run_pipeline", fast_pipeline)

    # Make burst / fire schedule synchronously (no thread hop) so tests
    # don't race.
    def sync_submit(fn, *a, **kw):
        kw.pop("tier", None)
        return fn(*a, **kw)

    monkeypatch.setattr(app_module, "submit_job", sync_submit)

    return app_module


def _fire(client, service="checkout-api", desc="p99 latency 4s"):
    return client.post(
        "/api/incidents/fire",
        data=json.dumps({"service": service, "severity": "SEV-2", "description": desc}),
        content_type="application/json",
    )


# ──────────────────────────────────────────────────────────────────────────
# Health / readiness
# ──────────────────────────────────────────────────────────────────────────


class TestReadiness:
    def test_health_minimal(self, app_module):
        client = app_module.app.test_client()
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True

    def test_readiness_deep_ok(self, app_module):
        client = app_module.app.test_client()
        r = client.get("/api/readiness")
        # We're OK if status 200 with ok=true OR 503 — but at minimum the
        # checks dict must exist and be inspectable. We assert 200 since
        # mock provider + memory checkpointer are healthy.
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert "graph" in body["checks"]
        assert "checkpointer" in body["checks"]


# ──────────────────────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────────────────────


class TestAuthEnforcement:
    def test_fire_succeeds_when_auth_off(self, app_module):
        client = app_module.app.test_client()
        r = _fire(client)
        assert r.status_code == 200

    def test_fire_rejected_without_token_when_auth_on(self, app_module, monkeypatch):
        monkeypatch.setenv("SRE_AUTH_REQUIRED", "1")
        client = app_module.app.test_client()
        r = _fire(client)
        assert r.status_code == 401

    def test_fire_accepted_with_correct_scope_token(self, app_module, monkeypatch):
        from sre_agent.auth import REGISTRY, Token

        monkeypatch.setenv("SRE_AUTH_REQUIRED", "1")
        REGISTRY.clear()
        REGISTRY.register(Token(name="oncall", secret="tok-fire", scopes=("fire",)))
        client = app_module.app.test_client()
        r = client.post(
            "/api/incidents/fire",
            data=json.dumps({"service": "x", "severity": "SEV-3", "description": "y"}),
            content_type="application/json",
            headers={"Authorization": "Bearer tok-fire"},
        )
        assert r.status_code == 200

    def test_auth_me_reports_state(self, app_module, monkeypatch):
        from sre_agent.auth import REGISTRY, Token

        monkeypatch.setenv("SRE_AUTH_REQUIRED", "1")
        REGISTRY.clear()
        REGISTRY.register(Token(name="reader", secret="tok-r", scopes=("read",)))
        client = app_module.app.test_client()

        # Without a token → 401
        r = client.get("/api/auth/me")
        assert r.status_code == 401

        # With token → 200 + scope info
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer tok-r"})
        assert r.status_code == 200
        body = r.get_json()
        assert body["enforced"] is True
        assert body["authenticated"] is True
        assert body["token_name"] == "reader"


# ──────────────────────────────────────────────────────────────────────────
# Rate limit
# ──────────────────────────────────────────────────────────────────────────


class TestRateLimit:
    def test_fire_429_when_over_limit(self, app_module, monkeypatch):
        from sre_agent.ratelimit import LIMITER

        monkeypatch.setenv("SRE_RATE_LIMIT", "on")
        monkeypatch.setenv("SRE_RATE_FIRE", "0.01:1")  # 1 burst
        LIMITER.reset()
        client = app_module.app.test_client()

        r1 = _fire(client)
        assert r1.status_code == 200

        r2 = _fire(client)
        assert r2.status_code == 429
        assert r2.headers.get("Retry-After") == "1"


# ──────────────────────────────────────────────────────────────────────────
# Feedback round-trip
# ──────────────────────────────────────────────────────────────────────────


class TestFeedbackFlow:
    def test_post_feedback_then_get(self, app_module):
        client = app_module.app.test_client()

        r = _fire(client)
        incident_id = r.get_json()["id"]

        r = client.post(
            f"/api/incidents/{incident_id}/feedback",
            data=json.dumps(
                {
                    "verdict": "thumbs_up",
                    "submitter": "alice",
                    "free_text": "looked right",
                }
            ),
            content_type="application/json",
        )
        assert r.status_code == 201
        fb_id = r.get_json()["feedback_id"]
        assert fb_id.startswith("fb-")

        # Read back
        r = client.get(f"/api/incidents/{incident_id}/feedback")
        assert r.status_code == 200
        body = r.get_json()
        assert len(body["records"]) == 1
        assert body["records"][0]["submitter"] == "alice"

    def test_summary_aggregates(self, app_module):
        client = app_module.app.test_client()
        for verdict in ("thumbs_up", "thumbs_up", "thumbs_down"):
            r = _fire(client)
            iid = r.get_json()["id"]
            client.post(
                f"/api/incidents/{iid}/feedback",
                data=json.dumps({"verdict": verdict}),
                content_type="application/json",
            )

        # Force re-aggregation since we tampered with disk indirectly
        from sre_agent.feedback import STORE

        STORE._totals_loaded = False

        r = client.get("/api/feedback/summary")
        body = r.get_json()
        assert body["positive"] >= 2
        assert body["negative"] >= 1
        assert body["csat"] is not None

    def test_feedback_404_for_unknown_incident(self, app_module):
        client = app_module.app.test_client()
        r = client.post(
            "/api/incidents/never-existed/feedback",
            data=json.dumps({"verdict": "thumbs_up"}),
            content_type="application/json",
        )
        assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────────────
# Slack actions
# ──────────────────────────────────────────────────────────────────────────


class TestSlackActions:
    def test_thumbs_up_converts_to_feedback(self, app_module):
        client = app_module.app.test_client()
        r = _fire(client)
        incident_id = r.get_json()["id"]

        payload = {
            "actions": [{"action_id": "sre_feedback_up", "value": incident_id}],
            "user": {"username": "bob"},
        }
        r = client.post(
            "/api/slack/actions",
            data={"payload": json.dumps(payload)},
        )
        assert r.status_code == 200
        body = r.get_json()
        assert body["verdict"] == "thumbs_up"

        # Verify the feedback landed in the store
        r = client.get(f"/api/incidents/{incident_id}/feedback")
        assert r.get_json()["records"][0]["submitter"] == "slack:bob"

    def test_unknown_incident_404(self, app_module):
        client = app_module.app.test_client()
        payload = {
            "actions": [{"action_id": "sre_feedback_up", "value": "nope"}],
            "user": {"username": "bob"},
        }
        r = client.post("/api/slack/actions", data={"payload": json.dumps(payload)})
        assert r.status_code == 404

    def test_signature_enforced_in_prod_mode(self, app_module, monkeypatch):
        monkeypatch.setenv("SRE_SLACK_VERIFY_REQUIRED", "1")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "shhh")
        client = app_module.app.test_client()

        r = _fire(client)
        incident_id = r.get_json()["id"]
        payload = {
            "actions": [{"action_id": "sre_feedback_up", "value": incident_id}],
            "user": {"username": "mallory"},
        }
        # No signature headers → 401
        r = client.post("/api/slack/actions", data={"payload": json.dumps(payload)})
        assert r.status_code == 401


# ──────────────────────────────────────────────────────────────────────────
# Harness summary surface
# ──────────────────────────────────────────────────────────────────────────


class TestHarnessSummary:
    def test_summary_includes_all_subsystems(self, app_module):
        client = app_module.app.test_client()
        r = client.get("/api/harness/summary")
        assert r.status_code == 200
        body = r.get_json()
        # Every L5 subsystem surfaces stats here for one-stop ops view.
        assert "recorder" in body
        assert "cache" in body
        assert "rate_limit" in body
        assert "feedback" in body
        assert "observability" in body
        assert body["observability"]["mode"] in {"off", "stdout", "langfuse", "otlp"}


class TestVariantsEndpoint:
    def test_variants_listed(self, app_module):
        client = app_module.app.test_client()
        r = client.get("/api/prompts/variants")
        assert r.status_code == 200
        body = r.get_json()
        agents = {a["agent"]: a for a in body["agents"]}
        assert "hypothesis-gen" in agents
        assert "conservative" in agents["hypothesis-gen"]["variants"]
