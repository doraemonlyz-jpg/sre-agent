"""Tests for the runbook_consultant node + its integration with the graph."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from sre_agent.nodes.runbook_consultant import runbook_consultant
from sre_agent.runbooks.store import reset_store_cache
from sre_agent.schemas import AlertIn, EvidenceResult, Severity


@pytest.fixture
def runbook_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the runbook subsystem at a temp dir with one service-specific chunk."""
    root = tmp_path / "rb"
    root.mkdir()
    (root / "checkout-api.md").write_text(
        "# Checkout API\n\n"
        "## Redis connection pool exhaustion after deploy\n\n"
        "> service: checkout-api\n"
        "> tags: redis, deploy, regression\n\n"
        "**Symptoms**: error_rate spike, ConnectionError logs.\n"
        "**Mitigation**: roll back the deploy.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SRE_RUNBOOKS_DIR", str(root))
    reset_store_cache()
    return root


def _alert(service: str, description: str, tags: list[str] | None = None) -> AlertIn:
    return AlertIn(
        service=service,
        severity=Severity.SEV_2,
        description=description,
        started_at=datetime.now(timezone.utc),
        tags=tags or [],
    )


def test_node_returns_found_when_library_matches(runbook_dir: Path) -> None:
    alert = _alert(
        "checkout-api",
        "error_rate spike with Redis ConnectionError after deploy",
        tags=["redis", "deploy"],
    )
    out = runbook_consultant({"alert": alert})  # type: ignore[arg-type]
    ev = out["runbooks"]
    assert ev.result == EvidenceResult.FOUND
    assert len(ev.hits) >= 1
    assert ev.hits[0].service == "checkout-api"
    assert "checkout-api.md" in ev.hits[0].path
    assert ev.library_size == 1
    assert ev.backend == "keyword"
    # An event must be emitted so the dashboard activity feed picks it up.
    [event] = out["events"]
    assert event["agent"] == "runbook-consultant"
    assert event["kind"] == "evidence"


def test_node_returns_no_signal_when_library_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("SRE_RUNBOOKS_DIR", str(empty))
    reset_store_cache()
    alert = _alert("checkout-api", "anything")
    out = runbook_consultant({"alert": alert})  # type: ignore[arg-type]
    assert out["runbooks"].result == EvidenceResult.NO_SIGNAL
    assert out["runbooks"].library_size == 0
    assert out["runbooks"].hits == []


def test_node_returns_no_signal_when_query_misses(runbook_dir: Path) -> None:
    # Library has one Redis-pool chunk; a totally unrelated alert should miss.
    alert = _alert("checkout-api", "zzzzz qqqqq xxxxx", tags=[])
    out = runbook_consultant({"alert": alert})  # type: ignore[arg-type]
    assert out["runbooks"].result == EvidenceResult.NO_SIGNAL
    assert out["runbooks"].hits == []
    # We still report the library size — the UI uses that to differentiate
    # "no library configured" from "library exists but didn't match".
    assert out["runbooks"].library_size == 1


def test_node_emits_runbook_citations(runbook_dir: Path) -> None:
    alert = _alert(
        "checkout-api",
        "Redis ConnectionError flood after recent deploy regression",
        tags=["redis"],
    )
    out = runbook_consultant({"alert": alert})  # type: ignore[arg-type]
    citations = out["runbooks"].citations
    assert any(c.startswith("runbook:") for c in citations)
    assert any("checkout-api.md" in c for c in citations)


def test_node_excludes_chunks_tagged_to_other_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "rb"
    root.mkdir()
    (root / "checkout.md").write_text(
        "# C\n## Redis exhaustion\n> service: checkout-api\n\nRedis stuff", encoding="utf-8"
    )
    (root / "payments.md").write_text(
        "# P\n## Redis exhaustion\n> service: payments\n\nRedis stuff", encoding="utf-8"
    )
    monkeypatch.setenv("SRE_RUNBOOKS_DIR", str(root))
    reset_store_cache()

    alert = _alert("payments", "Redis exhaustion in payments")
    out = runbook_consultant({"alert": alert})  # type: ignore[arg-type]
    # Only payments-tagged chunk should come back.
    services = {h.service for h in out["runbooks"].hits}
    assert services == {"payments"}
