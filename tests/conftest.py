"""
Pytest config & shared fixtures.

We block all real network egress for tests by pointing the LLM factory at an
unreachable host. The graph's fallback paths must produce a valid result
without ever calling an LLM.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make `dashboard.app` importable from tests (dashboard/ lives at the repo root).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture(autouse=True)
def _no_real_llm(monkeypatch):
    """
    Force the LLM factory to point at an unreachable Ollama. Any LLM call
    inside a node will raise; nodes must catch and fall back.
    """
    monkeypatch.setenv("SRE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SRE_LOG_LEVEL", "ERROR")
    # Pin retrieval to the deterministic keyword backend so we never reach
    # for a network embedding model during tests.
    monkeypatch.setenv("SRE_EMBEDDINGS_BACKEND", "keyword")
    # Isolate checkpoints per test run.
    monkeypatch.setenv("SRE_STATE_DIR", os.environ.get("SRE_STATE_DIR", ".state/test"))
    # Drop the lru_cache on the model factory so the env vars actually win.
    from sre_agent.models.factory import get_chat_model
    get_chat_model.cache_clear()
    # Drop the runbook store singleton so each test sees a fresh store
    # (especially important when a test overrides SRE_RUNBOOKS_DIR).
    from sre_agent.runbooks.store import reset_store_cache
    reset_store_cache()
