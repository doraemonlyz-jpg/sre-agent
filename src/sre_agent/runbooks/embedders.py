"""
Embedding backends for runbook retrieval.

We support three tiers, in order of "quality if available":

  openai   text-embedding-3-small via langchain-openai
  ollama   nomic-embed-text via langchain-ollama (local, free)
  keyword  hand-rolled TF-IDF-ish — zero deps, deterministic, OK for tests
            and good enough to demo retrieval wiring without any model.

The factory is environment-driven and **fails-soft**: if the configured
backend can't be constructed (missing API key, ollama not running, etc.)
we drop back to KeywordBackend rather than crashing. The runbook node
treats retrieval as best-effort — a missing match is fine, a missing
*service* is not.

Env:

    SRE_EMBEDDINGS_BACKEND   'auto' (default) | 'openai' | 'ollama' | 'keyword'
    SRE_EMBEDDINGS_MODEL     model override; defaults vary per backend
    OPENAI_API_KEY           required for openai
    OLLAMA_BASE_URL          required for ollama (default http://localhost:11434)
"""

from __future__ import annotations

import logging
import math
import os
import re
from abc import ABC, abstractmethod
from collections import Counter
from typing import Any

logger = logging.getLogger("sre_agent.runbooks.embedders")


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


# ──────────────────────────────────────────────────────────────────────────
# Public ABC
# ──────────────────────────────────────────────────────────────────────────


class EmbeddingBackend(ABC):
    """Implementations score (query, candidate) pairs in [0, 1]."""

    name: str = "unknown"

    @abstractmethod
    def index(self, texts: list[str]) -> list[Any]:
        """Pre-compute representations for the candidate corpus."""

    @abstractmethod
    def query(self, text: str) -> Any:
        """Compute a representation for a search query."""

    @abstractmethod
    def score(self, query_repr: Any, candidate_repr: Any) -> float:
        """Return a similarity in [0, 1] — higher = more relevant."""


# ──────────────────────────────────────────────────────────────────────────
# Keyword (TF-IDF-ish) backend — zero deps, deterministic, the test default
# ──────────────────────────────────────────────────────────────────────────


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]+")
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for", "with",
    "is", "are", "was", "were", "be", "by", "as", "this", "that", "it", "its",
    "from", "but", "not", "no", "we", "you", "your", "our", "if", "so", "than",
    "then", "do", "does", "did", "will", "can", "have", "has", "had",
})


def _tokens(text: str) -> list[str]:
    return [
        t.lower() for t in _WORD_RE.findall(text)
        if len(t) > 1 and t.lower() not in _STOPWORDS
    ]


class KeywordBackend(EmbeddingBackend):
    """
    Hand-rolled TF-IDF cosine over tokenized text.

    Not a great embedder; great fallback. Critically: deterministic,
    zero-network, zero-dep — so the entire test suite can rely on it.
    """

    name = "keyword"

    def __init__(self) -> None:
        self._idf: dict[str, float] = {}
        self._n_docs: int = 0

    def index(self, texts: list[str]) -> list[Counter]:
        self._n_docs = max(1, len(texts))
        df: Counter = Counter()
        token_lists: list[list[str]] = []
        for t in texts:
            toks = _tokens(t)
            token_lists.append(toks)
            for w in set(toks):
                df[w] += 1
        # Smoothed IDF: 1 + log((1+N)/(1+df)).  The leading +1 keeps the
        # weight nonzero when N=1 (otherwise log(1)=0 and a single-doc
        # library scores everything 0). The +1s in the log argument are
        # add-one smoothing for unseen words.
        self._idf = {
            w: 1.0 + math.log((1.0 + self._n_docs) / (1.0 + d))
            for w, d in df.items()
        }
        return [self._to_vec(t) for t in token_lists]

    def query(self, text: str) -> Counter:
        return self._to_vec(_tokens(text))

    def _to_vec(self, toks: list[str]) -> Counter:
        if not toks:
            return Counter()
        tf = Counter(toks)
        norm = max(1, len(toks))
        return Counter({
            w: (c / norm) * self._idf.get(w, 0.0)
            for w, c in tf.items()
        })

    def score(self, query_repr: Counter, candidate_repr: Counter) -> float:
        if not query_repr or not candidate_repr:
            return 0.0
        common = set(query_repr) & set(candidate_repr)
        if not common:
            return 0.0
        dot = sum(query_repr[w] * candidate_repr[w] for w in common)
        nq = math.sqrt(sum(v * v for v in query_repr.values()))
        nc = math.sqrt(sum(v * v for v in candidate_repr.values()))
        if nq <= 0 or nc <= 0:
            return 0.0
        # Squeeze into [0, 1] — TF-IDF cosine is already roughly there.
        return max(0.0, min(1.0, dot / (nq * nc)))


# ──────────────────────────────────────────────────────────────────────────
# LangChain-backed dense embedding adapter
# ──────────────────────────────────────────────────────────────────────────


class LangChainEmbeddingBackend(EmbeddingBackend):
    """Wraps any langchain `Embeddings` object."""

    def __init__(self, embeddings: Any, name: str) -> None:
        self._emb = embeddings
        self.name = name

    def index(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._emb.embed_documents(texts)

    def query(self, text: str) -> list[float]:
        return self._emb.embed_query(text)

    def score(self, query_repr: list[float], candidate_repr: list[float]) -> float:
        return max(0.0, min(1.0, (_cosine(query_repr, candidate_repr) + 1.0) / 2.0))


# ──────────────────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────────────────


def get_embedder(name: str | None = None) -> EmbeddingBackend:
    """
    Choose an embedding backend.  'auto' tries openai → ollama → keyword.
    Returns a working backend or KeywordBackend on every failure path.
    """
    choice = (name or os.environ.get("SRE_EMBEDDINGS_BACKEND", "auto")).lower()

    def _try_openai() -> EmbeddingBackend | None:
        if not os.environ.get("OPENAI_API_KEY"):
            return None
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError:
            return None
        try:
            model = os.environ.get("SRE_EMBEDDINGS_MODEL", "text-embedding-3-small")
            return LangChainEmbeddingBackend(OpenAIEmbeddings(model=model), name="openai")
        except Exception as e:
            logger.warning("openai embeddings init failed: %s", e)
            return None

    def _try_ollama() -> EmbeddingBackend | None:
        try:
            from langchain_ollama import OllamaEmbeddings
        except ImportError:
            return None
        try:
            model = os.environ.get("SRE_EMBEDDINGS_MODEL", "nomic-embed-text")
            base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            # NOTE: we do NOT eagerly probe ollama here — that would slow boot
            # and we don't want to break with a network error during construction.
            # The first call to `index()` or `query()` will surface a failure
            # which the caller (RunbookStore) catches and falls back from.
            return LangChainEmbeddingBackend(
                OllamaEmbeddings(model=model, base_url=base_url),
                name="ollama",
            )
        except Exception as e:
            logger.warning("ollama embeddings init failed: %s", e)
            return None

    if choice == "keyword":
        return KeywordBackend()
    if choice == "openai":
        b = _try_openai()
        return b or KeywordBackend()
    if choice == "ollama":
        b = _try_ollama()
        return b or KeywordBackend()
    # auto
    return _try_openai() or _try_ollama() or KeywordBackend()
