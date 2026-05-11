"""
Runbook subsystem — the team's accumulated knowledge, made retrievable.

Public API:

    from sre_agent.runbooks import RunbookStore, get_store

    store = get_store()                       # singleton, configured by env
    hits = store.search("redis pool exhaustion on chaos-app", service="chaos-app", k=3)

`get_store()` is process-wide cached. The first call loads + chunks every
markdown file under `runbooks/`, embeds them with whichever backend is
configured, and keeps them in memory for the rest of the process. Tests
override the path via `SRE_RUNBOOKS_DIR`.
"""

from __future__ import annotations

from sre_agent.runbooks.chunker import RunbookChunk, chunk_file, chunk_text
from sre_agent.runbooks.embedders import (
    EmbeddingBackend,
    KeywordBackend,
    get_embedder,
)
from sre_agent.runbooks.store import RunbookStore, get_store

__all__ = [
    "EmbeddingBackend",
    "KeywordBackend",
    "RunbookChunk",
    "RunbookStore",
    "chunk_file",
    "chunk_text",
    "get_embedder",
    "get_store",
]
