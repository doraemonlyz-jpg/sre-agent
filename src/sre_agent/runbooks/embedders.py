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
# BM25 backend (C1) -- real ranking algorithm, still zero-dep
#
# Why BM25 not TF-IDF cosine
# --------------------------
# TF-IDF cosine is a similarity, not a ranking model. BM25 is the de-facto
# industrial standard for ranked retrieval (Elasticsearch / Lucene /
# OpenSearch all use it as their default scorer). The two tunable
# parameters `k1` (term-saturation) and `b` (length normalisation) are
# chosen to match the Lucene defaults so behaviour is portable.
#
# For our use-case (10-100 runbook chunks, queries 5-25 tokens),
# BM25 dominates cosine in precision-at-1 because it knows:
#   * Term saturation: 5 occurrences of "OOM" isn't 5x better than 1.
#   * Length penalty: a 4-line chunk and a 40-line chunk that BOTH
#     mention "OOM" once -- the short one is more likely on-topic.
# Cosine has neither effect.
# ──────────────────────────────────────────────────────────────────────────


class BM25Backend(EmbeddingBackend):
    """
    Okapi BM25 ranking over tokenized runbook chunks.

    Implementation notes:
      * `index()` stores doc-level token counts + lengths. We return
        the doc indices as opaque "representations" -- score lookups
        go through `_score_doc()` which references the indexed state.
      * `score()` is intentionally O(|query_terms|), not the whole
        vocabulary -- BM25's strength is that you only iterate over
        the words actually in the query.
      * Output scores are squashed into [0, 1] with a soft cutoff so
        downstream confidence checks behave like the other backends.
    """

    name = "bm25"
    k1: float = 1.2  # Lucene default
    b: float = 0.75  # Lucene default

    def __init__(self) -> None:
        self._doc_lens: list[int] = []
        self._doc_tfs: list[Counter] = []
        self._idf: dict[str, float] = {}
        self._avg_len: float = 0.0
        self._n_docs: int = 0
        # Kept for backward-compat with persisted indexes from earlier
        # snapshots. We no longer use it at score time -- see score().
        self._max_score_seen: float = 1.0

    def index(self, texts: list[str]) -> list[int]:
        token_lists: list[list[str]] = [_tokens(t) for t in texts]
        self._doc_lens = [len(toks) for toks in token_lists]
        self._doc_tfs = [Counter(toks) for toks in token_lists]
        self._n_docs = max(1, len(texts))
        self._avg_len = sum(self._doc_lens) / self._n_docs if self._n_docs else 0.0

        df: Counter = Counter()
        for toks in token_lists:
            for w in set(toks):
                df[w] += 1
        # Robertson-Sparck-Jones IDF with +0.5 smoothing and max(0, .)
        # floor to keep negative IDFs from punishing common-but-relevant
        # terms.
        self._idf = {
            w: max(
                0.0,
                math.log((self._n_docs - d + 0.5) / (d + 0.5) + 1.0),
            )
            for w, d in df.items()
        }

        # Return one opaque "representation" per doc: the doc index.
        return list(range(self._n_docs))

    def query(self, text: str) -> set:
        return set(_tokens(text))

    def _score_doc_idx_by_terms(self, qterms: set, doc_idx: int) -> float:
        if not qterms or doc_idx >= len(self._doc_tfs):
            return 0.0
        tf = self._doc_tfs[doc_idx]
        dl = self._doc_lens[doc_idx]
        score = 0.0
        for w in qterms:
            if w not in tf or w not in self._idf:
                continue
            f = tf[w]
            idf = self._idf[w]
            num = f * (self.k1 + 1.0)
            denom = f + self.k1 * (1.0 - self.b + self.b * (dl / (self._avg_len or 1.0)))
            score += idf * (num / (denom or 1.0))
        return score

    def score(self, query_repr: set, candidate_repr: int) -> float:
        # Squash BM25 raw scores (unbounded above) into a [0, 1] range
        # via a soft sigmoid-ish saturator. We use 1 - exp(-raw / scale)
        # where `scale` is a conservative typical-good-match value. This
        # preserves rank ordering AND keeps the score in [0, 1] without
        # collapsing the corpus the way max-normalisation did. A truly
        # great match (raw ~10) lands at ~0.93; a noise hit (raw ~0.5)
        # lands at ~0.05.
        raw = self._score_doc_idx_by_terms(query_repr, candidate_repr)
        if raw <= 0.0:
            return 0.0
        return 1.0 - math.exp(-raw / 4.0)


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
    if choice == "bm25":
        return BM25Backend()
    if choice == "openai":
        b = _try_openai()
        return b or BM25Backend()
    if choice == "ollama":
        b = _try_ollama()
        return b or BM25Backend()
    # auto: try dense embeddings, then BM25 (better than keyword TF-IDF
    # for ranked retrieval), then keyword as the last-line fallback.
    return _try_openai() or _try_ollama() or BM25Backend()
