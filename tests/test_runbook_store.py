"""Unit tests for the RunbookStore: indexing, service filtering, retrieval."""

from __future__ import annotations

from pathlib import Path

import pytest

from sre_agent.runbooks.embedders import KeywordBackend
from sre_agent.runbooks.store import RunbookStore


@pytest.fixture
def tmp_library(tmp_path: Path) -> Path:
    """A tiny ad-hoc library: two service-specific runbooks + one generic."""
    root = tmp_path / "rb"
    root.mkdir()
    (root / "checkout-api.md").write_text(
        "# Checkout API\n\n"
        "## Redis pool exhaustion after deploy\n\n"
        "> service: checkout-api\n"
        "> tags: redis, deploy, regression\n\n"
        "Symptoms: rapid error_rate spike, ConnectionError logs.\n"
        "Mitigation: roll back the deploy with kubectl rollout undo.\n",
        encoding="utf-8",
    )
    (root / "payments.md").write_text(
        "# Payments\n\n"
        "## Stripe webhook retries flooding\n\n"
        "> service: payments\n"
        "> tags: stripe, webhook\n\n"
        "Symptoms: Stripe webhook handler latency p99 spike, retry storms.\n",
        encoding="utf-8",
    )
    (root / "general").mkdir()
    (root / "general" / "cascade.md").write_text(
        "# Cascade\n\n"
        "## Walking the dependency graph backwards\n\n"
        "> tags: cascade, downstream\n\n"
        "When a service alerts but its own metrics are fine, look at "
        "downstream callees and their hot spans.\n",
        encoding="utf-8",
    )
    return root


def test_store_loads_all_chunks(tmp_library: Path) -> None:
    store = RunbookStore.from_directory(tmp_library, backend=KeywordBackend())
    assert store.size == 3
    paths = sorted({ic.chunk.path for ic in store.chunks})
    # Relative paths, posix-style.
    assert any("checkout-api.md" in p for p in paths)
    assert any("payments.md" in p for p in paths)
    assert any("cascade.md" in p for p in paths)


def test_store_skips_readme(tmp_path: Path) -> None:
    root = tmp_path / "rb"
    root.mkdir()
    (root / "README.md").write_text("# README\n\n## Should be skipped\n\nignore me", encoding="utf-8")
    (root / "real.md").write_text("# Real\n\n## A real chunk\n\nkeep me", encoding="utf-8")
    store = RunbookStore.from_directory(root, backend=KeywordBackend())
    assert store.size == 1
    assert store.chunks[0].chunk.title == "A real chunk"


def test_missing_directory_yields_empty_store(tmp_path: Path) -> None:
    store = RunbookStore.from_directory(tmp_path / "nope", backend=KeywordBackend())
    assert store.size == 0
    assert store.search("anything") == []


def test_service_filter_excludes_other_services(tmp_library: Path) -> None:
    store = RunbookStore.from_directory(tmp_library, backend=KeywordBackend())
    hits = store.search("redis pool exhaustion deploy", service="checkout-api", k=5)
    services = [h.chunk.service for h in hits]
    # We can see chunks tagged to checkout-api OR untagged (general).
    # We must NEVER see a chunk tagged to a different service.
    assert "payments" not in services
    # And we expect the checkout-api chunk to be the top hit.
    assert hits[0].chunk.service == "checkout-api"


def test_service_filter_allows_generic_chunks(tmp_library: Path) -> None:
    store = RunbookStore.from_directory(tmp_library, backend=KeywordBackend())
    # Cross-cutting query: should pull in the general cascade chunk.
    hits = store.search("cascade downstream walking dependency graph", service="checkout-api", k=5)
    services = [h.chunk.service for h in hits]
    assert None in services  # the generic chunk made it through the filter


def test_search_returns_empty_for_irrelevant_query(tmp_library: Path) -> None:
    store = RunbookStore.from_directory(tmp_library, backend=KeywordBackend())
    # Nonsense query — keyword score should be ~zero, below min_score.
    hits = store.search("zzzzz qqqqq xxxxxx", service="checkout-api", k=5)
    assert hits == []


def test_search_respects_k_limit(tmp_library: Path) -> None:
    store = RunbookStore.from_directory(tmp_library, backend=KeywordBackend())
    hits = store.search("redis deploy cascade downstream", k=1)
    assert len(hits) == 1


def test_search_top_hit_is_service_specific_over_generic(tmp_library: Path) -> None:
    """
    When a query matches both a service-specific runbook and a generic
    one, the service-specific should rank higher because it contains the
    service name token in its body.
    """
    store = RunbookStore.from_directory(tmp_library, backend=KeywordBackend())
    hits = store.search(
        "redis pool exhaustion deploy regression",
        service="checkout-api",
        k=3,
    )
    assert hits[0].chunk.service == "checkout-api"
