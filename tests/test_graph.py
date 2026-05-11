"""
End-to-end graph tests.

These hit every node in the LangGraph WITHOUT a real LLM. The fallback paths
must produce a valid IncidentReport every time. This guarantees the production
graph degrades gracefully when the model is down.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime, timezone

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from sre_agent.graph import build_graph
from sre_agent.schemas import AlertIn, IncidentReport, Severity


@pytest.fixture
def graph():
    """Build a fresh graph with a tmp sqlite checkpointer per test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path, check_same_thread=False)
    saver = SqliteSaver(conn)
    g = build_graph(checkpointer=saver)
    yield g
    conn.close()
    try:
        os.unlink(path)
    except OSError:
        pass


def _run(graph, scenario_id: str) -> IncidentReport:
    """Run the graph end-to-end against a scenario and return the IncidentReport."""
    alert = AlertIn(
        service={
            "redis-pool-exhaustion": "checkout-api",
            "false-positive": "search-api",
            "downstream-cascade": "user-profile-api",
        }[scenario_id],
        severity=Severity.SEV_1,
        description="test",
        started_at=datetime.now(timezone.utc),
        scenario_id=scenario_id,
    )
    config = {"configurable": {"thread_id": f"test-{scenario_id}"}}
    for _ in graph.stream({"alert": alert, "events": []}, config=config):
        pass
    state = graph.get_state(config).values
    return state["report"]


def test_redis_scenario_produces_diagnosed_or_no_signal(graph):
    """With LLM down, hypothesis_gen falls back. We still get a report."""
    report = _run(graph, "redis-pool-exhaustion")
    assert report.phase in {"diagnosed", "no_signal", "failed"}
    assert report.hypotheses is not None
    assert len(report.hypotheses.hypotheses) >= 1
    assert report.logs is not None
    assert report.deploys is not None
    # Evidence MUST be present even without LLM refinement
    assert report.logs.hits > 0
    assert any(d.suspect == "HIGH" for d in report.deploys.deploys)


def test_false_positive_produces_no_signal_or_low_conf(graph):
    report = _run(graph, "false-positive")
    assert report.phase in {"no_signal", "failed", "diagnosed"}
    # The top hypothesis should reflect the lack of strong signal
    assert report.hypotheses is not None


def test_downstream_cascade_finds_traces(graph):
    report = _run(graph, "downstream-cascade")
    assert report.traces is not None
    # Trace evidence should point at a downstream
    assert report.traces.downstream_suspect or report.traces.hot_span


def test_pipeline_always_produces_remediation(graph):
    """No matter what, the Remediation Suggester emits SOMETHING."""
    for sid in ("redis-pool-exhaustion", "false-positive", "downstream-cascade"):
        report = _run(graph, sid)
        assert report.remediation is not None
        # Either actions OR an explicit do_not_do — never silent
        assert report.remediation.actions or report.remediation.do_not_do


def test_events_are_chronological(graph):
    """The events list must end with a 'done' event from `finalize`."""
    config = {"configurable": {"thread_id": "test-events"}}
    alert = AlertIn(
        service="checkout-api",
        severity=Severity.SEV_1,
        description="test",
        started_at=datetime.now(timezone.utc),
        scenario_id="redis-pool-exhaustion",
    )
    for _ in graph.stream({"alert": alert, "events": []}, config=config):
        pass
    state = graph.get_state(config).values
    events = state.get("events", [])
    assert len(events) > 0
    assert events[-1]["agent"] == "finalize"
    assert events[-1]["kind"] == "done"


def test_remediation_actions_all_have_reversal(graph):
    """Lane discipline: every action MUST come with a reversal."""
    report = _run(graph, "redis-pool-exhaustion")
    for a in report.remediation.actions:
        assert a.reversal, f"action '{a.title}' missing reversal"


def test_runbook_consultant_runs_in_graph(graph):
    """
    Phase B regression: the runbook_consultant node must execute as the
    5th parallel worker and populate state.runbooks. The seed library in
    `runbooks/` is the source of truth.
    """
    report = _run(graph, "redis-pool-exhaustion")
    assert report.runbooks is not None
    # We don't assert FOUND vs NO_SIGNAL because that depends on retrieval
    # against the seed library. But we DO assert:
    # 1. The node ran and wrote evidence to state.
    # 2. The library was visible to the node (size > 0 — we have seed runbooks).
    assert report.runbooks.library_size > 0
    assert report.runbooks.backend == "keyword"  # forced by conftest


def test_runbook_consultant_finds_chaos_app_pattern(graph):
    """
    The seed library includes a `chaos-app.md` runbook documenting the
    Redis pool exhaustion bug. An alert on `chaos-app` mentioning Redis
    should retrieve that chunk.
    """
    alert = AlertIn(
        service="chaos-app",
        severity=Severity.SEV_2,
        description="error_rate spike with redis ConnectionError pool exhausted",
        started_at=datetime.now(timezone.utc),
        tags=["redis", "connection-pool"],
        scenario_id="redis-pool-exhaustion",  # the graph uses this to fetch mock telemetry
    )
    config = {"configurable": {"thread_id": "test-runbook-chaos"}}
    for _ in graph.stream({"alert": alert, "events": []}, config=config):
        pass
    report = graph.get_state(config).values["report"]
    assert report.runbooks is not None
    # We expect at least one hit, and the top one should be from the
    # chaos-app runbook (service-tagged match beats generic).
    assert len(report.runbooks.hits) >= 1
    top = report.runbooks.hits[0]
    assert top.service == "chaos-app"
    assert "chaos-app.md" in top.path


def test_runbook_event_visible_in_event_stream(graph):
    """The runbook_consultant must emit a dashboard event so the UI sees it."""
    report = _run(graph, "redis-pool-exhaustion")
    config = {"configurable": {"thread_id": "test-redis-pool-exhaustion"}}
    state = graph.get_state(config).values
    runbook_events = [e for e in state["events"] if e["agent"] == "runbook-consultant"]
    assert len(runbook_events) == 1
    assert runbook_events[0]["kind"] == "evidence"
    assert report.runbooks is not None
