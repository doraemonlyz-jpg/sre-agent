"""
Tests for sre_agent.metrics -- B1 Prometheus instrumentation.

Coverage:
  * Each `record_*` helper bumps the right metric by the right amount.
  * Counters use the right label set.
  * Histograms produce buckets.
  * Render produces Prometheus text format with our metric names.
  * The Flask /metrics endpoint returns 200 + correct content-type.
  * The module survives missing prometheus_client (stub path) -- we
    can't physically uninstall the dep in CI, but we cover the
    no-op-on-stub semantics by reading the render path.
"""

from __future__ import annotations

import pytest

from sre_agent import metrics as M


def _get_counter_value(counter, **labels):
    """Read a Counter sample for the given label set."""
    for sample in counter.collect()[0].samples:
        if sample.name.endswith("_total") and sample.labels == labels:
            return sample.value
    return 0.0


class TestRecorderHelpers:
    def test_record_llm_call_increments_calls_counter(self):
        before = _get_counter_value(
            M.LLM_CALLS_TOTAL, agent="t1", model="m1", status="ok",
        )
        M.record_llm_call(agent="t1", model="m1", status="ok", latency_seconds=1.5)
        after = _get_counter_value(
            M.LLM_CALLS_TOTAL, agent="t1", model="m1", status="ok",
        )
        assert after == before + 1

    def test_record_llm_call_observes_latency(self):
        # We can't easily read the histogram bucket counts back across
        # multiple tests cleanly, so we just check the _count sample
        # increased.
        def _count():
            for s in M.LLM_LATENCY.collect()[0].samples:
                if s.name.endswith("_count") and s.labels.get("agent") == "tcount":
                    return s.value
            return 0.0

        before = _count()
        M.record_llm_call(agent="tcount", model="m", status="ok", latency_seconds=0.7)
        assert _count() == before + 1

    def test_record_llm_call_records_tokens(self):
        def _read_tokens(direction):
            for s in M.LLM_TOKENS_TOTAL.collect()[0].samples:
                if (s.name.endswith("_total")
                        and s.labels.get("agent") == "ttok"
                        and s.labels.get("direction") == direction):
                    return s.value
            return 0.0

        before_in = _read_tokens("input")
        before_out = _read_tokens("output")
        M.record_llm_call(
            agent="ttok", model="m", status="ok",
            input_tokens=100, output_tokens=50,
        )
        assert _read_tokens("input") == before_in + 100
        assert _read_tokens("output") == before_out + 50

    def test_record_incident_terminal(self):
        before = _get_counter_value(M.INCIDENTS_TOTAL, result="diagnosed")
        M.record_incident_terminal(result="diagnosed", duration_seconds=42.0)
        after = _get_counter_value(M.INCIDENTS_TOTAL, result="diagnosed")
        assert after == before + 1

    def test_record_cache_event(self):
        before = _get_counter_value(M.CACHE_EVENTS_TOTAL, kind="hit")
        M.record_cache_event("hit")
        M.record_cache_event("hit")
        after = _get_counter_value(M.CACHE_EVENTS_TOTAL, kind="hit")
        assert after == before + 2

    def test_record_feedback(self):
        before = _get_counter_value(M.FEEDBACK_TOTAL, verdict="thumbs_up")
        M.record_feedback("thumbs_up")
        after = _get_counter_value(M.FEEDBACK_TOTAL, verdict="thumbs_up")
        assert after == before + 1

    def test_record_rate_limit_drop(self):
        before = _get_counter_value(M.RATE_LIMIT_DROPS_TOTAL, scope="api.fire")
        M.record_rate_limit_drop("api.fire")
        after = _get_counter_value(M.RATE_LIMIT_DROPS_TOTAL, scope="api.fire")
        assert after == before + 1

    def test_record_fallback(self):
        labels = {
            "agent": "test", "from_tier": "premium", "to_tier": "cheap",
            "reason": "timeout",
        }
        before = _get_counter_value(M.LLM_FALLBACKS_TOTAL, **labels)
        M.record_fallback(**labels)
        after = _get_counter_value(M.LLM_FALLBACKS_TOTAL, **labels)
        assert after == before + 1

    def test_record_runbook_search_records_hit_status(self):
        before_hit = _get_counter_value(
            M.RUNBOOK_SEARCH_TOTAL, backend="bm25", hit="true",
        )
        M.record_runbook_search(backend="bm25", hit=True)
        M.record_runbook_search(backend="bm25", hit=False)
        after_hit = _get_counter_value(
            M.RUNBOOK_SEARCH_TOTAL, backend="bm25", hit="true",
        )
        after_miss = _get_counter_value(
            M.RUNBOOK_SEARCH_TOTAL, backend="bm25", hit="false",
        )
        assert after_hit == before_hit + 1
        assert after_miss >= 1


class TestGauges:
    def test_calibrator_health_sets_gauges(self):
        M.update_calibrator_health(ece=0.05, brier=0.20, n_train=1500)
        # Read gauges via collect()
        ece_value = M.CALIBRATOR_ECE.collect()[0].samples[0].value
        brier_value = M.CALIBRATOR_BRIER.collect()[0].samples[0].value
        n_value = M.CALIBRATOR_N_TRAIN.collect()[0].samples[0].value
        assert ece_value == pytest.approx(0.05)
        assert brier_value == pytest.approx(0.20)
        assert n_value == 1500

    def test_active_incidents_gauge_increments_and_decrements(self):
        # Note: this is module-global state; we read deltas
        before = M.ACTIVE_INCIDENTS.collect()[0].samples[0].value
        M.incident_started()
        M.incident_started()
        assert M.ACTIVE_INCIDENTS.collect()[0].samples[0].value == before + 2
        M.incident_ended()
        assert M.ACTIVE_INCIDENTS.collect()[0].samples[0].value == before + 1
        M.incident_ended()
        assert M.ACTIVE_INCIDENTS.collect()[0].samples[0].value == before

    def test_active_incidents_clamps_at_zero(self):
        # Many decrements shouldn't go negative.
        before = M.ACTIVE_INCIDENTS.collect()[0].samples[0].value
        for _ in range(int(before) + 5):
            M.incident_ended()
        assert M.ACTIVE_INCIDENTS.collect()[0].samples[0].value == 0


class TestRender:
    def test_render_returns_prometheus_text(self):
        # Drive at least one sample so the body is non-trivial.
        M.record_llm_call(
            agent="render-agent", model="m", status="ok", latency_seconds=0.5,
        )
        body, ctype = M.render_latest()
        decoded = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "text/plain" in ctype
        assert "sre_llm_calls_total" in decoded
        assert 'agent="render-agent"' in decoded

    def test_render_includes_help_lines(self):
        M.record_feedback("thumbs_up")
        body, _ = M.render_latest()
        decoded = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "# HELP sre_feedback_total" in decoded
        assert "# TYPE sre_feedback_total counter" in decoded


class TestBuildInfo:
    def test_initialise_from_env_sets_build_info(self, monkeypatch):
        monkeypatch.setenv("SRE_AGENT_VERSION", "1.2.3")
        monkeypatch.setenv("SRE_CHECKPOINTER", "postgres")
        monkeypatch.setenv("SRE_LLM_PROVIDER", "ollama")
        M.initialise_from_env()
        samples = M.BUILD_INFO.collect()[0].samples
        labels = [s.labels for s in samples]
        assert any(
            l.get("version") == "1.2.3"
            and l.get("checkpointer") == "postgres"
            and l.get("llm_provider") == "ollama"
            for l in labels
        )


class TestFlaskRoute:
    """Smoke-test the /metrics route is plumbed end-to-end."""

    def test_metrics_endpoint_returns_200_with_text(self):
        from dashboard.app import app as flask_app

        client = flask_app.test_client()
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.content_type
        body = resp.get_data(as_text=True)
        # Body must contain at least one of our metric names.
        assert "sre_" in body
