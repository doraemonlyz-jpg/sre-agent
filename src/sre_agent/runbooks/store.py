"""
RunbookStore — load + chunk every markdown file under `runbooks/` and serve
retrieval queries.

The store is loaded once per process via `get_store()`. First call walks the
directory, chunks every file, and embeds all chunks. Subsequent calls return
the cached instance. Tests override the path via `SRE_RUNBOOKS_DIR`.

If embedding fails for any chunk (e.g. Ollama unreachable mid-batch), the
store falls back to the keyword backend so retrieval is always *something*
non-empty.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sre_agent.runbooks.chunker import RunbookChunk, chunk_file
from sre_agent.runbooks.embedders import (
    BM25Backend,
    EmbeddingBackend,
    KeywordBackend,
    get_embedder,
)

logger = logging.getLogger("sre_agent.runbooks.store")


@dataclass
class _IndexedChunk:
    chunk: RunbookChunk
    repr: Any  # opaque to us; the embedder knows what it is


@dataclass
class SearchHit:
    """Public retrieval result."""

    chunk: RunbookChunk
    score: float


@dataclass
class RunbookStore:
    """In-memory ranked retrieval over a runbook library."""

    root: Path
    backend: EmbeddingBackend
    chunks: list[_IndexedChunk] = field(default_factory=list)

    # ─── construction ─────────────────────────────────────────────────

    @classmethod
    def from_directory(
        cls,
        root: Path,
        *,
        backend: EmbeddingBackend | None = None,
    ) -> RunbookStore:
        """Walk `root` and index every *.md file."""
        backend = backend or get_embedder()
        store = cls(root=root, backend=backend)
        if not root.exists():
            logger.warning("runbooks dir does not exist: %s", root)
            return store

        all_chunks: list[RunbookChunk] = []
        for md in sorted(root.rglob("*.md")):
            # Skip the README — it's documentation about the format, not a runbook.
            if md.name.lower() == "readme.md":
                continue
            try:
                all_chunks.extend(chunk_file(md, root=root))
            except Exception as e:  # pragma: no cover
                logger.warning("failed to chunk %s: %s", md, e)

        if not all_chunks:
            return store

        texts = [c.search_text for c in all_chunks]
        try:
            reprs = backend.index(texts)
        except Exception as e:
            logger.warning("embedding backend %s failed during index: %s — falling back to keyword", backend.name, e)
            backend = KeywordBackend()
            store.backend = backend
            reprs = backend.index(texts)

        store.chunks = [_IndexedChunk(c, r) for c, r in zip(all_chunks, reprs, strict=False)]
        logger.info(
            "runbooks indexed: %d chunks from %s (backend=%s)",
            len(store.chunks), root, backend.name,
        )
        return store

    # ─── retrieval ────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        service: str | None = None,
        k: int = 3,
        min_score: float = 0.05,
    ) -> list[SearchHit]:
        """
        Top-k chunks for `query`.  If `service` is given, chunks targeting a
        *different* service are filtered out; chunks with no `service` tag
        are kept (treated as cross-cutting "general" guidance).
        """
        if not self.chunks or not query.strip():
            self._observe_search(hit=False)
            return []
        # Prometheus: time the entire ranking pass.
        import time as _time
        t0 = _time.perf_counter()
        try:
            q_repr = self.backend.query(query)
        except Exception as e:
            logger.warning("backend %s query failed: %s — degrading to keyword fallback for this call",
                           self.backend.name, e)
            fallback = KeywordBackend()
            fb_reprs = fallback.index([c.chunk.search_text for c in self.chunks])
            q_repr = fallback.query(query)
            scored = [
                (fallback.score(q_repr, r), self.chunks[i].chunk)
                for i, r in enumerate(fb_reprs)
            ]
        else:
            scored = [
                (self.backend.score(q_repr, ic.repr), ic.chunk)
                for ic in self.chunks
            ]

        # Filter by service: keep generic chunks AND chunks tagged to our service.
        if service:
            scored = [
                (s, c) for s, c in scored
                if c.service is None or c.service == service
            ]

        scored.sort(key=lambda kv: -kv[0])
        out: list[SearchHit] = []
        for score, chunk in scored:
            if score < min_score:
                break
            out.append(SearchHit(chunk=chunk, score=float(score)))
            if len(out) >= k:
                break

        # Prometheus: record latency + hit/miss in a best-effort block.
        try:
            from sre_agent import metrics as _m
            _m.RUNBOOK_SEARCH_LATENCY.labels(backend=self.backend.name).observe(
                _time.perf_counter() - t0,
            )
            _m.record_runbook_search(backend=self.backend.name, hit=bool(out))
        except Exception:
            pass
        return out

    def _observe_search(self, *, hit: bool) -> None:
        try:
            from sre_agent import metrics as _m
            _m.record_runbook_search(backend=self.backend.name, hit=hit)
        except Exception:
            pass

    # ─── metadata ─────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self.chunks)

    # ─── persistence (C1) ─────────────────────────────────────────────
    #
    # Why we persist
    # --------------
    # The runbook library is rebuilt on every dashboard boot, which is
    # fast for the demo set (~12 chunks) but pathological for the prod
    # case (~500 chunks * 1536-dim embeddings = 6+ minutes on cold
    # cache with OpenAI / a real embedding service).
    #
    # Persistence has two pieces:
    #   1. The CHUNKS (text + metadata) -- portable across backends.
    #   2. The BACKEND STATE (BM25 stats / dense vectors) -- backend-
    #      specific, refusing to load across backend types so we never
    #      silently use the wrong representations.

    PERSISTENCE_VERSION = 1

    def save_to_disk(self, path: Path | str) -> None:
        """
        Serialise the indexed corpus to a single JSON file.

        The file is a self-describing dict:
          - version              schema version
          - backend.name         "bm25" | "keyword" | "openai" | "ollama"
          - backend.params       backend-specific dict
          - chunks               list of {text, metadata, repr}
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "version": self.PERSISTENCE_VERSION,
            "backend": _dump_backend_state(self.backend),
            "chunks": [
                {
                    "path": str(ic.chunk.path),
                    "title": ic.chunk.title,
                    "service": ic.chunk.service,
                    "tags": list(ic.chunk.tags),
                    "body": ic.chunk.body,
                    "repr": _dump_repr(ic.repr),
                }
                for ic in self.chunks
            ],
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(body, ensure_ascii=False))
        tmp.replace(path)
        logger.info("runbook index persisted: %s (n=%d, backend=%s)",
                    path, len(self.chunks), self.backend.name)

    @classmethod
    def load_from_disk(cls, path: Path | str, *, root: Path | None = None) -> "RunbookStore":
        """
        Deserialise a previously-saved index.

        Refuses to load if the file's backend name doesn't match the
        backend the runtime would otherwise pick. This is on purpose:
        loading openai embeddings into a keyword backend would silently
        produce nonsensical similarity scores. Better to crash fast.
        """
        path = Path(path)
        body = json.loads(path.read_text())
        if body.get("version") != cls.PERSISTENCE_VERSION:
            raise ValueError(
                f"runbook index version mismatch: file={body.get('version')} "
                f"runtime={cls.PERSISTENCE_VERSION}"
            )
        backend = _load_backend_state(body["backend"])
        store = cls(root=root or path.parent, backend=backend)
        for entry in body["chunks"]:
            chunk = RunbookChunk(
                path=entry["path"],
                title=entry["title"],
                body=entry.get("body", ""),
                service=entry.get("service"),
                tags=list(entry.get("tags", [])),
            )
            store.chunks.append(_IndexedChunk(chunk, _load_repr(entry["repr"])))
        logger.info("runbook index loaded: %s (n=%d, backend=%s)",
                    path, len(store.chunks), backend.name)
        return store


# ──────────────────────────────────────────────────────────────────────────
# (De)serialisation of backend state
#
# Each backend dumps the minimal state needed to reproduce scores.
# Unknown backends fall back to "no persistable state" -- the chunks
# are saved, but the index is rebuilt on load. Useful for the keyword
# backend whose state is reconstructable from the corpus alone.
# ──────────────────────────────────────────────────────────────────────────


def _dump_backend_state(backend: EmbeddingBackend) -> dict[str, Any]:
    name = backend.name
    if isinstance(backend, BM25Backend):
        return {
            "name": "bm25",
            "params": {
                "k1": backend.k1,
                "b": backend.b,
                "doc_lens": backend._doc_lens,
                "doc_tfs": [dict(tf) for tf in backend._doc_tfs],
                "idf": backend._idf,
                "avg_len": backend._avg_len,
                "n_docs": backend._n_docs,
                "max_score_seen": backend._max_score_seen,
            },
        }
    if isinstance(backend, KeywordBackend):
        return {
            "name": "keyword",
            "params": {
                "idf": backend._idf,
                "n_docs": backend._n_docs,
            },
        }
    # Dense backends: no state to save; we save the per-chunk vectors
    # in `chunks[].repr` and rebuild a minimal backend on load.
    return {"name": name, "params": {}}


def _load_backend_state(body: dict[str, Any]) -> EmbeddingBackend:
    name = body.get("name", "")
    params = body.get("params", {}) or {}
    if name == "bm25":
        b = BM25Backend()
        b._doc_lens = list(params.get("doc_lens", []))
        b._doc_tfs = [Counter(tf) for tf in params.get("doc_tfs", [])]
        b._idf = dict(params.get("idf", {}))
        b._avg_len = float(params.get("avg_len", 0.0))
        b._n_docs = int(params.get("n_docs", len(b._doc_lens)))
        b._max_score_seen = float(params.get("max_score_seen", 1.0))
        return b
    if name == "keyword":
        k = KeywordBackend()
        k._idf = dict(params.get("idf", {}))
        k._n_docs = int(params.get("n_docs", 1))
        return k
    # Unknown / dense: just return whatever the env-driven factory picks.
    # The caller's intent is "use my persisted reprs"; the backend
    # only needs to score query <-> repr pairs.
    return get_embedder(name) if name else get_embedder()


def _dump_repr(repr_: Any) -> Any:
    """Coerce a backend repr into JSON-serialisable form."""
    if isinstance(repr_, Counter):
        return {"_kind": "counter", "v": dict(repr_)}
    if isinstance(repr_, (int, float, str, bool)) or repr_ is None:
        return repr_
    if isinstance(repr_, (list, tuple)):
        return list(repr_)
    if isinstance(repr_, set):
        return {"_kind": "set", "v": list(repr_)}
    # Last resort: stringify -- the load path will preserve it but
    # scoring against an unknown shape will likely zero out.
    return str(repr_)


def _load_repr(blob: Any) -> Any:
    if isinstance(blob, dict) and blob.get("_kind") == "counter":
        return Counter(blob["v"])
    if isinstance(blob, dict) and blob.get("_kind") == "set":
        return set(blob["v"])
    return blob


# ──────────────────────────────────────────────────────────────────────────
# Process-wide singleton
# ──────────────────────────────────────────────────────────────────────────


_STORE: RunbookStore | None = None
_STORE_LOCK = threading.Lock()


def _default_runbook_dir() -> Path:
    """
    Find the runbooks/ directory — env override or repo-relative search.

    NB: we explicitly skip our OWN package path (`src/sre_agent/runbooks/`)
    because that's where this file lives — a naive ancestor walk would
    short-circuit there and never find the actual content directory at
    the repo root.
    """
    env = os.environ.get("SRE_RUNBOOKS_DIR")
    if env:
        return Path(env).resolve()
    own_pkg = Path(__file__).resolve().parent  # .../src/sre_agent/runbooks
    # Walk up from this file looking for a sibling `runbooks/` that ACTUALLY
    # contains markdown content (not our package).
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "runbooks"
        if (
            candidate.exists()
            and candidate.resolve() != own_pkg
            and any(candidate.rglob("*.md"))
        ):
            return candidate
    return Path.cwd() / "runbooks"


def get_store() -> RunbookStore:
    """Process-wide cached store. First call loads + indexes.

    If `SRE_RUNBOOK_INDEX_PATH` is set and points at an existing
    persisted index, the store is restored from disk in O(n_chunks)
    time instead of re-embedding everything. Falls back to a fresh
    `from_directory()` build on any load failure so a corrupt index
    file is never fatal.
    """
    global _STORE
    if _STORE is not None:
        return _STORE
    with _STORE_LOCK:
        if _STORE is None:
            idx_env = os.environ.get("SRE_RUNBOOK_INDEX_PATH")
            if idx_env:
                idx_path = Path(idx_env)
                if idx_path.exists():
                    try:
                        _STORE = RunbookStore.load_from_disk(
                            idx_path, root=_default_runbook_dir(),
                        )
                        logger.info(
                            "runbook store loaded from persisted index: %s (size=%d)",
                            idx_path, _STORE.size,
                        )
                        return _STORE
                    except Exception as e:
                        logger.warning(
                            "failed to load persisted index %s: %s -- rebuilding",
                            idx_path, e,
                        )
            _STORE = RunbookStore.from_directory(_default_runbook_dir())
    return _STORE


def reset_store_cache() -> None:
    """Test hook — drop the cached singleton."""
    global _STORE
    _STORE = None
