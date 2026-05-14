# Architecture Decision Records

This folder contains the load-bearing decisions behind sre-agent.
Each ADR follows a trimmed [MADR](https://adr.github.io/madr/) format:

- **Context** — what was the problem
- **Decision** — what we chose
- **Considered** — what we ruled out and why
- **Consequences** — what this commits us to (good and bad)

Add a new ADR when you make a decision that is hard to undo, or that
a new contributor would have to ask "why did you do this?" about.

## Index

| #   | Status     | Title                                                     |
| --- | ---------- | --------------------------------------------------------- |
| 001 | Accepted   | [LangGraph as the orchestrator](./001-langgraph.md)       |
| 002 | Accepted   | [SQLite for checkpoints in dev, Postgres in prod](./002-sqlite-vs-postgres.md) |
| 003 | Accepted   | [BM25 for runbook RAG, no vector DB](./003-bm25-no-vector-db.md) |
| 004 | Accepted   | [3-tier LLM fallback chain](./004-fallback-chain.md)      |
| 005 | Accepted   | [Synthetic data for L6 self-improvement](./005-synthetic-data.md) |
| 006 | Accepted   | [No autonomous execution of remediations](./006-no-auto-execute.md) |
| 007 | Accepted   | [Ensemble via threads, not asyncio refactor](./007-ensemble-via-threads.md) |

## Status vocabulary

- **Proposed** — discussion in flight; not yet binding.
- **Accepted** — what the codebase reflects today.
- **Superseded by ADR-NNN** — the decision was reversed; pointer to the new one.
- **Deprecated** — the area is being removed entirely.

We never delete ADRs; superseded ones stay so newcomers can read the
history. Editing an old ADR's body after it's accepted is a code smell —
write a new one and supersede it.
