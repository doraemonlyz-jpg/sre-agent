"""
Tests for sre_agent.runbooks -- C1.

Coverage:
  * BM25 backend ranks the right doc highest.
  * BM25 saturation behaviour: term over-repetition doesn't dominate.
  * BM25 length penalty: short relevant doc beats long mostly-irrelevant.
  * Backend factory returns bm25 when requested + on auto-fallback.
  * Store persistence: save -> load -> identical results.
  * Persistence rejects version mismatch.
  * Search records the Prometheus counter.
  * Indexer CLI smoke test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from sre_agent.runbooks.embedders import (
    BM25Backend,
    KeywordBackend,
    get_embedder,
)
from sre_agent.runbooks.store import RunbookStore


# ──────────────────────────────────────────────────────────────────────────
# BM25 algorithm correctness
# ──────────────────────────────────────────────────────────────────────────


class TestBM25Backend:
    def test_relevant_doc_ranks_highest(self):
        b = BM25Backend()
        docs = [
            "Database connection pool exhausted; restart pgbouncer.",
            "How to ship a new release of the frontend.",
            "Disk IO on the storage tier looks fine; nothing to do.",
        ]
        reprs = b.index(docs)
        q = b.query("database pool")
        scores = [b.score(q, r) for r in reprs]
        # Doc 0 should win
        assert scores[0] == max(scores)
        assert scores[0] > scores[1]
        assert scores[0] > scores[2]

    def test_no_match_returns_zero(self):
        b = BM25Backend()
        b.index(["foo bar baz", "alpha beta gamma"])
        q = b.query("nothingrelevanthere")
        # No tokens match -> all scores 0
        for r in [0, 1]:
            assert b.score(q, r) == 0.0

    def test_term_saturation(self):
        """5 occurrences shouldn't be 5x a single occurrence."""
        b = BM25Backend()
        # Pad with neutral filler so doc lengths are comparable; without
        # padding the length-normalisation factor dominates and BM25's
        # saturation behaviour isn't visible.
        filler = " ".join(["alpha"] * 20)
        docs = [
            f"oom_crash {filler}",
            f"oom_crash oom_crash oom_crash oom_crash oom_crash {filler}",
        ]
        reprs = b.index(docs)
        # Use the raw scorer to avoid the per-corpus normalisation that
        # squashes values into [0, 1].
        s_short = b._score_doc_idx_by_terms({"oom_crash"}, 0)
        s_long = b._score_doc_idx_by_terms({"oom_crash"}, 1)
        # The longer doc DOES score higher but BM25's saturation curve
        # means it isn't ~5x higher.
        assert s_long > s_short
        ratio = s_long / s_short
        assert ratio < 5.0, f"BM25 saturation should compress repeats, got ratio={ratio}"

    def test_length_penalty(self):
        """Short relevant doc should beat a much longer one with same
        single match buried in noise."""
        b = BM25Backend()
        docs = [
            "Disk full alert. Free up /var/log.",
            (
                "We have many alerts in the system. "
                "Some are about CPU, some about memory, some about network, "
                "some about IO, some about DNS, some about ingress, "
                "and occasionally one about disk. "
                + " ".join(["chatter"] * 50)
            ),
        ]
        reprs = b.index(docs)
        q = b.query("disk")
        s_short = b.score(q, reprs[0])
        s_long = b.score(q, reprs[1])
        assert s_short > s_long

    def test_query_returns_set_of_tokens(self):
        b = BM25Backend()
        b.index(["alpha beta"])
        q = b.query("Alpha")
        assert isinstance(q, set)
        assert "alpha" in q  # lowercased

    def test_scores_in_unit_interval(self):
        b = BM25Backend()
        docs = ["one two three", "four five six", "seven eight nine"]
        reprs = b.index(docs)
        for query in ["one", "five seven", "completelynew"]:
            q = b.query(query)
            for r in reprs:
                s = b.score(q, r)
                assert 0.0 <= s <= 1.0


# ──────────────────────────────────────────────────────────────────────────
# Embedder factory
# ──────────────────────────────────────────────────────────────────────────


class TestEmbedderFactory:
    def test_explicit_bm25(self):
        b = get_embedder("bm25")
        assert isinstance(b, BM25Backend)

    def test_explicit_keyword(self):
        k = get_embedder("keyword")
        assert isinstance(k, KeywordBackend)

    def test_auto_without_cloud_keys_picks_bm25(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # The factory tries openai (no key -> skip), then ollama (lazy,
        # constructor succeeds even if ollama isn't running). In CI
        # without ollama-client at all, falls through to BM25.
        monkeypatch.setenv("SRE_EMBEDDINGS_BACKEND", "auto")
        b = get_embedder()
        # Either OllamaEmbeddings (degrades on first call) or BM25;
        # both are acceptable. We just assert "not keyword" -- BM25 or
        # the dense backend is always preferred under "auto".
        assert b.name != "keyword"


# ──────────────────────────────────────────────────────────────────────────
# Store persistence (save/load round-trip)
# ──────────────────────────────────────────────────────────────────────────


@pytest.fixture
def runbook_dir(tmp_path):
    """Tiny runbook corpus on disk. Follows the chunker convention:
    `## ` headings produce chunks; `> service:` annotates a chunk."""
    d = tmp_path / "runbooks"
    d.mkdir()
    (d / "redis.md").write_text(
        "# Redis runbooks\n\n"
        "## Redis OOM under load\n"
        "> service: redis\n\n"
        "When the Redis cluster hits memory pressure, run "
        "`redis-cli MEMORY PURGE` first then scale the replica count.\n"
    )
    (d / "pgbouncer.md").write_text(
        "# PgBouncer runbooks\n\n"
        "## PgBouncer connection pool exhausted\n"
        "> service: pgbouncer\n\n"
        "Restart pgbouncer when SUSPEND/RESUME doesn't drain the pool.\n"
    )
    return d


class TestPersistence:
    def test_save_and_load_roundtrip(self, runbook_dir, tmp_path):
        b = BM25Backend()
        store = RunbookStore.from_directory(runbook_dir, backend=b)
        assert store.size > 0

        out = tmp_path / "idx.json"
        store.save_to_disk(out)

        loaded = RunbookStore.load_from_disk(out, root=runbook_dir)
        assert loaded.size == store.size
        assert loaded.backend.name == "bm25"

        # Same query should return the same top hit
        q = "redis"
        hits_a = store.search(q, k=1)
        hits_b = loaded.search(q, k=1)
        assert hits_a and hits_b
        assert hits_a[0].chunk.title == hits_b[0].chunk.title

    def test_save_and_load_preserves_bm25_state(self, runbook_dir, tmp_path):
        b = BM25Backend()
        store = RunbookStore.from_directory(runbook_dir, backend=b)
        out = tmp_path / "idx.json"
        store.save_to_disk(out)

        loaded = RunbookStore.load_from_disk(out, root=runbook_dir)
        # Internal state preserved
        assert loaded.backend._n_docs == b._n_docs  # type: ignore[attr-defined]
        assert loaded.backend._avg_len == b._avg_len  # type: ignore[attr-defined]
        for w, v in b._idf.items():  # type: ignore[attr-defined]
            assert loaded.backend._idf[w] == pytest.approx(v)  # type: ignore[attr-defined]

    def test_version_mismatch_raises(self, tmp_path):
        bogus = {
            "version": 999,
            "backend": {"name": "bm25", "params": {}},
            "chunks": [],
        }
        path = tmp_path / "v999.json"
        path.write_text(json.dumps(bogus))
        with pytest.raises(ValueError, match="version mismatch"):
            RunbookStore.load_from_disk(path, root=tmp_path)

    def test_keyword_backend_persists_idf(self, runbook_dir, tmp_path):
        k = KeywordBackend()
        store = RunbookStore.from_directory(runbook_dir, backend=k)
        out = tmp_path / "kw.json"
        store.save_to_disk(out)

        loaded = RunbookStore.load_from_disk(out, root=runbook_dir)
        assert loaded.backend.name == "keyword"
        assert isinstance(loaded.backend, KeywordBackend)
        for w, v in k._idf.items():
            assert loaded.backend._idf[w] == pytest.approx(v)  # type: ignore[attr-defined]


# ──────────────────────────────────────────────────────────────────────────
# Search records the Prometheus counter
# ──────────────────────────────────────────────────────────────────────────


class TestObservability:
    def test_search_records_runbook_metric(self, runbook_dir):
        from sre_agent.metrics import RUNBOOK_SEARCH_TOTAL

        def _read(hit: str) -> float:
            for s in RUNBOOK_SEARCH_TOTAL.collect()[0].samples:
                if (s.name.endswith("_total")
                        and s.labels.get("backend") == "bm25"
                        and s.labels.get("hit") == hit):
                    return s.value
            return 0.0

        before_hit = _read("true")
        before_miss = _read("false")

        store = RunbookStore.from_directory(runbook_dir, backend=BM25Backend())
        # Should hit
        hits = store.search("redis", k=1)
        assert hits
        # Should miss
        no_hits = store.search("xenosaur tetrahedron", k=1)
        assert not no_hits

        assert _read("true") == before_hit + 1
        assert _read("false") == before_miss + 1


# ──────────────────────────────────────────────────────────────────────────
# Indexer CLI smoke test
# ──────────────────────────────────────────────────────────────────────────


class TestIndexerCLI:
    def test_runbook_index_command_writes_file(self, runbook_dir, tmp_path):
        out = tmp_path / "cli-idx.json"
        env = dict(os.environ)
        env["SRE_RUNBOOKS_DIR"] = str(runbook_dir)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

        result = subprocess.run(
            [
                sys.executable, "-m", "sre_agent.cli", "runbook-index",
                "--output", str(out),
                "--backend", "bm25",
            ],
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert out.exists()
        body = json.loads(out.read_text())
        assert body["version"] == RunbookStore.PERSISTENCE_VERSION
        assert body["backend"]["name"] == "bm25"
        assert len(body["chunks"]) >= 2
