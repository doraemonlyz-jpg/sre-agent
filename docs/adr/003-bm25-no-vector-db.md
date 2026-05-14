# ADR-003: BM25 for runbook RAG, no vector database

- **Status:** Accepted
- **Date:** 2026-04-22

## Context

The runbook consultant retrieves team-written incident playbooks
(`runbooks/*.md`) and surfaces the top matches to the hypothesis
generator. Two design questions:

1. Which ranking algorithm?
2. Which storage backend?

Real-world runbook corpuses are small (10s-1000s of files), text-only,
and updated by humans -- not the kind of corpus where a learned dense
embedding pays off.

## Decision

- **Ranking:** Okapi BM25 with Lucene defaults (`k1=1.2, b=0.75`),
  implemented in `src/sre_agent/runbooks/embedders.py:BM25Backend`.
- **Storage:** In-process Python dicts of `{term -> postings}`,
  serialised to a JSON file via `RunbookStore.save_to_disk` /
  `load_from_disk`. The CLI `sre-agent runbook-index` builds it.
- **Score normalisation:** sigmoid-style `1 - exp(-raw / 4.0)` so
  the [0, 1] range is interpretable for downstream ranking and
  `min_score` filtering.

We do **not** run a dense-embedding model and do **not** depend on
a vector database (FAISS, pgvector, Weaviate, Qdrant, etc.).

## Considered

- **OpenAI embeddings + FAISS / pgvector.** A great fit for a 100k-doc
  product knowledge base. For 200 runbooks it's overkill, takes a
  cold-boot embed pass, costs API tokens, and adds an external
  dependency. The keyword-overlap model fits the corpus shape.
- **Sentence-transformers locally + FAISS.** Removes the API cost
  but adds ~500MB of model weights and a cold-load. Latency on
  query-time embed is the same order as BM25; the hits aren't
  obviously better on our golden cases.
- **Pure substring search.** What we shipped first; abandoned because
  the score function had no signal -- everything was 0 or 1, and
  `min_score` filtering didn't work.
- **Hybrid (BM25 + dense rerank).** Tempting if accuracy plateaus.
  Easy to add later because the embedder is a swappable backend in
  the same factory.

## Consequences

- **Good:** zero external dependencies for retrieval. Boot time on a
  fresh checkout is ~50ms even with the 200-runbook fixtures.
- **Good:** persistent index means subsequent boots skip indexing
  entirely. Set `SRE_RUNBOOK_INDEX_PATH=./.state/runbook-index.json`
  and the CLI command builds it once.
- **Good:** BM25 is famously robust on short technical documents --
  the dominant signal in runbooks IS the keyword overlap (service
  names, error codes, library names).
- **Bad:** semantic-only matches won't fire (e.g. a query for "memory
  pressure" won't surface a runbook titled "OOMKill troubleshooting"
  unless one of those words actually appears). We mitigate by
  recommending runbook authors use both formal and colloquial terms
  in their headings.
- **Bad:** the index is an in-process dict. A dashboard with > 1
  replica re-builds the index per replica -- still cheap but
  documented in the ops runbook.
