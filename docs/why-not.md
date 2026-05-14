# Why we did NOT do X

A companion to [`docs/adr/`](./adr/README.md). ADRs document the
choices we made; this file documents the choices we deliberately
**didn't** make, and why. It exists so that interview reviewers,
contributors, and Future Us don't repeatedly propose ideas the team
has already evaluated and consciously declined.

This file is intentionally short on each item -- if a "why not" turns
into a long argument, it deserves an ADR of its own.

## Architecture

### Why not a vector database (FAISS / Weaviate / pgvector)?

The runbook corpus is tiny (10s-1000s of short technical docs) and
keyword-dominated -- exactly where BM25 wins on accuracy and beats
dense embeddings on cold-boot, dependencies, and operational
simplicity. See [ADR-003](./adr/003-bm25-no-vector-db.md).

### Why not full async / `astream`?

The dominant latency cost is the LLM provider's queue depth, not the
Python event loop. Switching the whole graph to async is high-risk
for a marginal wall-clock win. Threads + a bounded fan-out helper
get the same useful subset (in-node ensemble) without the rewrite.
See [ADR-007](./adr/007-ensemble-via-threads.md).

### Why not let the agent execute remediations autonomously?

Two reasons: LLM confidence is systematically miscalibrated upward,
and the action set includes prod-mutating verbs (rollback, drain
node, scale to zero). The blast radius of the wrong call is
permanently larger than the cost of a 30-second human review.
See [ADR-006](./adr/006-no-auto-execute.md).

### Why not auto-merge the L6 cron PRs?

The whole point of opening a PR (instead of just writing the change
directly) is human review. CODEOWNERS gates the merge on
`@your-org/sre-leads` for prompts and `@your-org/ml-platform` for
the calibrator. Auto-merge would defeat the governance.

### Why not a JS/TS dashboard / Next.js frontend?

The dashboard is a single Flask app with vanilla HTML/CSS/JS so the
incident-response surface area stays in one process and one language.
The frontend is small (~1k LOC). A SPA would add a second build
pipeline, a second deploy, and CORS/auth surface for nothing
operational.

### Why not GraphQL?

Three REST endpoints (`/api/incidents`, `/api/feedback`,
`/api/incidents/<id>`) cover everything the dashboard needs. GraphQL
would mean adding a schema layer and a resolver framework to save
maybe one network round trip in the worst case.

## Observability

### Why not OpenTelemetry as the primary metrics path?

We export to Prometheus directly because the demo audience (interview
reviewers, single-laptop deploys) all have `prometheus-client`
working in 5 seconds. OpenTelemetry's Prometheus exporter is *also*
plumbed (set `OTEL_EXPORTER_OTLP_ENDPOINT`), but it's the second
path, not the first. The bias is "make the easy thing easy".

### Why not structured logs to ELK?

`structlog` writes JSON to stdout. Whatever log shipper your cluster
already runs (Fluent Bit, Vector, Loki Promtail, etc.) picks them
up. Bundling an ELK opinion would just add a thing to disable.

## LLM stack

### Why not LangChain Expression Language (LCEL) chains everywhere?

We use LCEL for the per-node LLM calls (the `llm | parser` pattern
inside each agent), but the orchestration is LangGraph. LCEL chains
don't checkpoint, can't fan-in deterministically, and can't stream
node-by-node events to the dashboard.

### Why not fine-tune a model on incident data?

We don't have enough real incident data, and even if we did, the
team that on-calls the agent is rarely the team that can fine-tune.
The L6 flywheel achieves "the agent gets better over time" via prompt
A/B testing and runbook drafting -- both of which any SRE can review
without ML expertise.

### Why not a 70B / Llama-3.1-70B local model as the primary tier?

The hardware bar (a 4090 or two) is higher than the audience for
this codebase has casual access to. The 3-tier fallback chain
(see [ADR-004](./adr/004-fallback-chain.md)) gives you the option:
plug in the 70B locally as Tier 1 if you have it; the same code
runs.

## Testing

### Why not 100% line coverage?

We aim for ~85% on critical paths (graph, harness, providers,
calibrator) and ignore the dashboard's HTML templating. Coverage
above ~90% on a project this size is dominated by enforcing tests
for code that doesn't merit them, not by catching real bugs.

### Why not property-based testing (Hypothesis)?

We considered it for `seed.py` distributions and the BM25 score
function. Both have well-understood behaviour and small, well-tested
input domains. Hypothesis would be valuable for a future "prompt
template synthesis" feature where the input space is large and
unstructured.

### Why not contract tests against real Datadog?

The `DatadogProvider` (cloud-tier; see `src/sre_agent/providers/`)
is exercised against `respx` mocks of the documented Datadog API
shape. Hitting real Datadog from CI would require a paid account,
storing credentials in CI secrets, and accepting that any Datadog
API change breaks our build for reasons unrelated to our code.
