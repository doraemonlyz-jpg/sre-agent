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

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sre_agent.runbooks.chunker import RunbookChunk, chunk_file
from sre_agent.runbooks.embedders import (
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
            return []
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
        return out

    # ─── metadata ─────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self.chunks)


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
    """Process-wide cached store. First call loads + indexes."""
    global _STORE
    if _STORE is not None:
        return _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = RunbookStore.from_directory(_default_runbook_dir())
    return _STORE


def reset_store_cache() -> None:
    """Test hook — drop the cached singleton."""
    global _STORE
    _STORE = None
