# Runbook library

The SRE Agent's "team brain". Every `*.md` file in this directory is split
into chunks by `##` headings and indexed at startup. The `runbook_consultant`
agent retrieves the top-k most relevant chunks for each incident and feeds
them into the Hypothesis Generator and Remediation Suggester.

## Authoring format

```markdown
# File-level title (one)

Optional intro prose. Anything above the first `## ` heading is metadata
context only — it's not a retrievable chunk.

## A section name = one chunk

> service: checkout-api
> tags: redis, latency, pool

**Symptoms**: …
**Likely cause**: …
**Mitigation**:
1. …
2. …
**Prevention**: …
**Related**: PR #1234, runbook X
```

### Metadata fields (all optional)

* `> service: <name>` — restricts retrieval to incidents on this service.
  Chunks without a `service:` line are treated as cross-cutting (always
  eligible regardless of which service the alert is about).
* `> tags: <csv>` — informational; surfaced in citations.

Anything you write between `## ` and the next `## ` becomes the chunk body.
The chunker trims at ~2200 chars to keep LLM context budgets sane, so:

* **Bullet-heavy** beats prose-heavy.
* **One symptom + one root cause + one mitigation** per section.
* **Cite PRs / past incidents** with concrete IDs the LLM can echo back.

## Why this exists

Without this, the agents reason in a vacuum — they're general-purpose SRE
analysts staring at telemetry. The runbook library is what makes them
*your* on-call team: they've read about your service's known failure
modes, your team's playbooks, your incident history. The hypothesis
generator can cite "this matches the 2024-12 incident, see runbook
`chaos-app.md`" instead of inventing causes from first principles.

## File layout

```
runbooks/
├── chaos-app.md          # the demo target — connection pool leak
├── checkout-api.md       # matches the mock 'redis-pool-exhaustion' scenario
├── general/
│   ├── connection-pool-exhaustion.md
│   ├── cascading-failures.md
│   └── false-positive-playbook.md
```

Service-specific files at the top level; cross-cutting patterns in
`general/`. The chunker walks recursively — folder structure is for
humans, not for retrieval.

## Configuration

```bash
# Override the directory (useful for testing)
SRE_RUNBOOKS_DIR=/path/to/your/runbooks

# Embedding backend — auto picks openai → ollama → keyword
SRE_EMBEDDINGS_BACKEND=auto

# Pin a specific model
SRE_EMBEDDINGS_MODEL=text-embedding-3-small
```

If no embedding model is available, the system falls back to a hand-rolled
TF-IDF retriever (zero deps, deterministic). It's not as good as real
embeddings but plenty for a demo or interview, and the entire test suite
relies on it so we can run offline.
