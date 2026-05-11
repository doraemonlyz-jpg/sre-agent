# SRE Agent — Multi-Agent Incident Response

[![status](https://img.shields.io/badge/status-v1%20production-success)]()
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![langgraph](https://img.shields.io/badge/orchestration-LangGraph-purple)]()
[![tests](https://img.shields.io/badge/tests-30%20passing-brightgreen)]()

> An AI on-call team. A monitoring alert fires → 7 specialized agents fan out
> across logs / metrics / traces / deploys → a hypothesis generator ranks root
> causes with citations → a remediation suggester writes the fix.
> **The agents never execute remediation.** Diagnosis target: **< 90 seconds**.

---

## What changed in v1 (this branch)

v0 was a deterministic demo: agents were "simulated" by a Python script that
pretended to be a multi-agent system. v1 is a real production system:

| Layer | v0 | v1 |
|---|---|---|
| Orchestration | hand-rolled `threading.Thread` | **LangGraph** (parallel fan-out, conditional edges, checkpointing) |
| State | in-memory dict | **SQLite (dev) / Postgres (prod)** checkpointer — survives restarts |
| Model | none (text simulation) | **Ollama / OpenAI / Anthropic** via factory |
| Output | text strings | **Pydantic structured output** — LLM forced to return typed JSON |
| Failure mode | crash | **Graceful degradation** — every node has a rule-based fallback |
| Deploy | python script | **Docker + docker-compose + Postgres** |
| Tests | none | **30 pytest cases** covering schemas, mock provider, full graph, dashboard |

---

## Quick start

### Option A — local dev (no Docker)

```bash
git clone https://github.com/doraemonlyz-jpg/sre-agent.git
cd sre-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Try the CLI
sre-agent scenarios
sre-agent investigate --scenario redis-pool-exhaustion

# Or boot the dashboard
python dashboard/app.py     # http://127.0.0.1:5080
```

### Option B — Docker (production-shaped, with Postgres)

```bash
cp .env.example .env       # add OPENAI_API_KEY or leave blank for Ollama
docker compose up --build  # dashboard at http://localhost:5080
```

### Option C — local LLM (Ollama)

```bash
# Pre-pull the models
ollama pull qwen2.5-coder:7b
ollama pull gpt-oss:20b

# Tell the agent to use Ollama
export SRE_LLM_PROVIDER=ollama
sre-agent investigate --scenario redis-pool-exhaustion
```

### Option D — full open-source demo (Prometheus + Loki + buggy app)

A self-contained world where the agent runs against **real** observability
infrastructure instrumenting a deliberately buggy service. See
[`demo-stack/`](demo-stack/README.md) for the full 60-second recipe.

```bash
# Bring up Prometheus + Loki + Grafana + chaos-app
docker compose -f demo-stack/docker-compose.yml up -d --build

# Point the SRE Agent at it
export SRE_DATA_PROVIDER=oss
export PROMETHEUS_URL=http://localhost:9090
export LOKI_URL=http://localhost:3100
python dashboard/app.py

# In another terminal: generate load until /redis-leak exhausts the
# "pool", then fire a webhook alert
./demo-stack/scripts/generate-load.sh 80
./demo-stack/scripts/fire-alert.sh
```

The dashboard now shows 8 agents fanning out across real Prometheus +
Loki APIs, producing a ranked root-cause hypothesis with confidence and
supporting evidence. **This is the demo to record for an interview.**

---

## Architecture

```
                ┌──────────────┐
                │ incident_pm  │   open incident
                └──────┬───────┘
                       │
        ┌─────────┬────┴────┬─────────┬──────────────┐
        ▼         ▼         ▼         ▼              ▼
   log_detec  metrics_  trace_rdr  deploy_hist  runbook_consult    (parallel)
        │      analyst    │           │              │
        └─────────┴───────┴───────────┴──────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │ hypothesis_gen   │   live telemetry + team's runbooks
                     └─────────┬────────┘
                               ▼
                     ┌──────────────────┐
                     │ remediation_sug  │   suggest fix, cite runbook commands
                     └─────────┬────────┘
                               ▼
                     ┌──────────────────┐
                     │     finalize     │   write IncidentReport
                     └──────────────────┘
                               ▼
                              END
```

**Eight agents in three layers:**

1. **`incident_pm`** — opens the incident, emits the kickoff event.
2. **Five parallel workers** —
   - `log_detective` / `metrics_analyst` / `trace_reader` / `deploy_historian`
     gather *live telemetry* from whatever provider you configure
     (mock / Datadog / Prometheus+Loki).
   - **`runbook_consultant`** retrieves *prior knowledge* — the team's
     runbooks (`runbooks/*.md`) via RAG over OpenAI / Ollama / TF-IDF
     embeddings. This is the moat: the agent doesn't reason in a vacuum,
     it brings your team's accumulated knowledge to every incident.
3. **`hypothesis_gen` → `remediation_sug` → `finalize`** — synthesize a
   ranked diagnosis and a safe action plan, citing both telemetry *and*
   the runbook chunks that match the failure mode.

Each node is a small Python function that:

1. Reads typed state from `GraphState` (TypedDict)
2. Optionally calls a `DataProvider` (mock / Datadog / Prometheus / Loki) or the `RunbookStore`
3. Optionally calls an LLM via `.with_structured_output(SomePydanticModel)`
4. Returns a partial dict; LangGraph merges via reducer

The whole pipeline is **checkpointed** — if the dashboard pod crashes mid-incident,
the graph resumes from the last completed node on restart.

See [DESIGN.md](DESIGN.md) for the full architecture.

---

## Layout

```
sre-agent/
├── src/sre_agent/           # the Python package
│   ├── schemas.py            # Pydantic: AlertIn, EvidenceBlock, Hypothesis, …
│   ├── graph.py              # LangGraph wiring
│   ├── state.py              # (see schemas.py — GraphState lives there)
│   ├── nodes/                # one file per agent
│   │   ├── incident_pm.py
│   │   ├── log_detective.py
│   │   ├── metrics_analyst.py
│   │   ├── trace_reader.py
│   │   ├── deploy_historian.py
│   │   ├── runbook_consultant.py     # ← Phase B: the team-knowledge layer
│   │   ├── hypothesis_gen.py
│   │   └── remediation_sug.py
│   ├── runbooks/             # ← Phase B: RAG subsystem
│   │   ├── chunker.py        # markdown → chunks
│   │   ├── embedders.py      # OpenAI / Ollama / TF-IDF backends
│   │   └── store.py          # indexed, service-filtered retrieval
│   ├── providers/
│   │   ├── base.py           # DataProvider ABC
│   │   ├── mock.py           # uses mocks/scenarios.json
│   │   ├── datadog.py        # real Datadog API
│   │   ├── prometheus.py     # metrics-only OSS provider
│   │   ├── loki.py           # logs-only OSS provider
│   │   └── composite.py      # mix-and-match providers per evidence type
│   ├── models/factory.py     # Ollama / OpenAI / Anthropic factory
│   ├── personas.py           # loads personas/*.md as system prompts
│   ├── logging.py            # structlog setup
│   └── cli.py                # `sre-agent ...` Typer CLI
├── personas/                 # 8 agent personas (markdown, used as system prompts)
├── runbooks/                 # ← Phase B: the team brain
│   ├── chaos-app.md          #     one file per service…
│   ├── checkout-api.md       #     …each `## section` becomes one chunk
│   └── general/              #     cross-cutting patterns (cascade, false-positive, …)
├── mocks/scenarios.json      # 3 demo incidents
├── dashboard/                # Flask UI; backend just spawns LangGraph runs
├── tests/                    # pytest, 111 cases, fully offline
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Configuration

Every knob is an environment variable. See `.env.example` for the full list.

| Var | Default | Purpose |
|---|---|---|
| `SRE_LLM_PROVIDER` | auto | `openai` / `anthropic` / `ollama` |
| `SRE_LLM_ORCHESTRATOR` | per-provider | model used by PM, Hypothesis, Remediation |
| `SRE_LLM_WORKER` | per-provider | model used by the 4 parallel workers |
| `SRE_DATA_PROVIDER` | `mock` | `mock` reads scenarios.json; `datadog` (v1.1) hits the real API |
| `SRE_CHECKPOINTER` | `sqlite` | `sqlite` (local file) or `postgres` (prod) |
| `DATABASE_URL` | – | Postgres DSN, used when `SRE_CHECKPOINTER=postgres` |
| `SRE_DASHBOARD_PORT` | `5080` | the Flask UI port |

---

## Safety properties

These are enforced by the type system, not by prompts:

| Property | How |
|---|---|
| **Agents never execute remediation** | `RemediationPlan.actions` is a list of `(title, command, reversal)` triples — only shown in UI |
| **Every remediation has a reversal** | Pydantic field required, validated at parse time |
| **Workers cannot hallucinate evidence** | Each `EvidenceResult` is `FOUND` / `NO_SIGNAL` / `ERROR` — typed enum, can't be prose |
| **Citations are typed** | `LogsEvidence.citations: list[str]` of log IDs; PM can re-query |
| **Graph survives restarts** | `SqliteSaver` / `PostgresSaver` checkpoints after every node |
| **LLM failure is graceful** | Every node has a rule-based fallback; tests pin LLM to unreachable host |

---

## Comparison

| Tool | Their angle | Ours |
|---|---|---|
| Resolve.ai ($35M Series A) | SaaS, auto-remediation | Self-hosted, local-first, human-in-the-loop |
| Cleric AI | SRE chat copilot | Webhook-driven pipeline, not chat |
| Datadog Bits AI | inline summaries | cross-tool correlation, structural citations |
| Honeycomb | "ask your logs" | "diagnose this alert end-to-end" |

Unique selling point: **the typed `EvidenceBlock` contract**. Most LLM ops
tools fail because they hallucinate citations. Pydantic schemas + structured
output mean ours physically cannot return a hypothesis without verifiable
log/trace/PR IDs the PM re-checks.

---

## Connecting to your stack

The Provider abstraction supports **Datadog** and a **Prometheus + Loki**
composite out of the box. Webhook ingestion accepts **Datadog Monitor /
PagerDuty / generic JSON** payloads.

| `SRE_DATA_PROVIDER` | logs | metrics | traces | deploys |
|---------------------|:----:|:-------:|:------:|:-------:|
| `mock` (default)    |  ✓   |    ✓    |   ✓    |    ✓    |
| `datadog`           |  ✓   |    ✓    |   ✓    |    ✓    |
| `prometheus`        |  —   |    ✓    |   —    |    —    |
| `loki`              |  ✓   |    —    |   —    |    —    |
| `oss` (prom+loki)   |  ✓   |    ✓    |   —    |    —    |

### Real-data Datadog provider

```bash
export SRE_DATA_PROVIDER=datadog
export DD_API_KEY=...
export DD_APP_KEY=...
export DD_SITE=datadoghq.com       # or datadoghq.eu, us3, ap1, ...
```

Mappings:

| Method            | Datadog endpoint                        |
|-------------------|-----------------------------------------|
| `fetch_logs`      | `POST /api/v2/logs/events/search`       |
| `fetch_metrics`   | `GET  /api/v1/query`   (5 std queries)  |
| `fetch_traces`    | `POST /api/v2/spans/events/search`      |
| `fetch_deploys`   | `GET  /api/v1/events?sources=deploy`    |

Network failures **never** raise — every API error becomes evidence with
`result=ERROR` so the graph keeps running with whatever partial signal it has.

### Inbound alert webhook

`POST /api/alerts/webhook` accepts three payload shapes, auto-detected:

```bash
# Datadog Monitor → Webhooks integration
curl -X POST http://localhost:5080/api/alerts/webhook \
  -H "Content-Type: application/json" \
  -d '{"alert_id":"99","alert_title":"err_rate","priority":"P1",
       "service":"checkout","tags":"env:prod","date":"2026-05-11T14:30:00Z"}'

# PagerDuty Webhook v3
curl -X POST http://localhost:5080/api/alerts/webhook \
  -d '{"event":{"event_type":"incident.triggered","data":{
       "title":"latency spike","service":{"summary":"checkout"},
       "urgency":"high","created_at":"2026-05-11T14:30:00Z"}}}'

# Generic — minimum contract
curl -X POST http://localhost:5080/api/alerts/webhook \
  -d '{"service":"checkout","description":"errors","severity":"high"}'
```

Force a specific adapter with `?source=datadog|pagerduty|generic` or
`X-SRE-Source` header. Set `SRE_WEBHOOK_SECRET` and have the sender include
`X-SRE-Token` to enable shared-secret auth.

### Slack notifications

```bash
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
# or force preview-only:
export SRE_SLACK_DRY_RUN=true
```

`POST /api/incidents/<id>/post-slack` either POSTs Block Kit JSON or returns
a dry-run preview the user can paste manually.

### Runbook RAG (Phase B — the team brain)

Every `*.md` file under `runbooks/` is chunked at startup, embedded, and made
searchable. The `runbook_consultant` agent runs in parallel with the four
telemetry workers and surfaces the top 3 most relevant chunks for each
incident. The hypothesis generator and remediation suggester both consume
those chunks and cite them by file path in their output.

```bash
# Backend auto-detects: OpenAI (if OPENAI_API_KEY) → Ollama → TF-IDF fallback
export SRE_EMBEDDINGS_BACKEND=auto        # 'openai' | 'ollama' | 'keyword'
export SRE_EMBEDDINGS_MODEL=text-embedding-3-small   # optional override
export SRE_RUNBOOKS_DIR=/path/to/runbooks            # default: ./runbooks
```

**Authoring** a runbook is just markdown. Each `## ` heading becomes one
retrievable chunk; optional `> service:` and `> tags:` lines on the first
lines of the section gate it to a specific service. See
[runbooks/README.md](runbooks/README.md) for the full format.

**Why this matters**: without it, the agents are general-purpose SRE
analysts staring at telemetry. With it, they're *your* on-call team —
they've read your service's known failure modes, your team's playbooks,
your incident history. Hypothesis output goes from "errors suggest a
Redis problem" to "this matches the documented connection-pool
exhaustion pattern in `runbooks/checkout-api.md`, mitigation is
`kubectl rollout undo`".

The TF-IDF fallback is intentional: zero dependencies, deterministic,
runs the entire test suite offline. Real embeddings improve recall but
aren't required to demo the system.

---

## Tests

```bash
pytest                       # 111 cases, no network, runs in ~25s
pytest --cov=sre_agent       # coverage report
```

The test suite **does not call any real LLM and never opens a socket**. The
Datadog provider and Slack notifier are exercised against their real response
shapes via `respx` — only the HTTP layer is faked, the parsers are the real
production code.

---

## What's still TODO (v1.1+)

- [x] Real Datadog provider (Logs API v2, Metrics v1, APM v2)
- [x] Webhook receiver (Datadog Monitor / PagerDuty / generic)
- [x] Real Slack notifier (Block Kit + dry-run mode)
- [x] Prometheus / Loki providers + open-source demo stack
- [x] Runbook RAG (8th agent — `runbook_consultant`, the team brain)
- [x] **Mocked production-scale**: bounded worker pool, burst endpoint, tier classifier (see Phase E below)
- [ ] Tempo / Jaeger provider for traces (open-source stack)
- [ ] Slack message buttons that POST back into `/api/incidents/<id>/action`
- [ ] OpenTelemetry tracing on every node
- [ ] Auth: bearer token + per-team isolation
- [ ] Eval suite: 10 hand-labeled historical incidents, accuracy ≥ 80%

---

## Phase E — production-scale roadmap (TikTok / hyper-scale)

The system today is **interview-ready** but not yet **TikTok-ready**. The
architectural insight remains: at hyper-scale, *raw* log/metric volume
(tens of millions of lines per minute) never touches the agent — that's
the telemetry backend's job (ByteLog / Datadog / ClickHouse). The agent
calls focused queries (one service, 15-minute window, error filter) and
reasons over the *bucketed* result, which is hundreds, not millions.

The actual bottlenecks at scale, and the planned upgrades:

| Bottleneck | Current state | Phase E upgrade |
|---|---|---|
| **Alert burst** (1000 alerts/min when a hub service dies) | Bounded `ThreadPoolExecutor`, mocked (`SRE_MAX_CONCURRENT=4`) | Webhook → Kafka / RocketMQ; Temporal workers; `_spawn_incident` becomes idempotent on `incident_id` |
| **LLM cost** ($1.5M/yr at 100k alerts/day on GPT-4o) | Three-tier classifier (`rule` / `cheap` / `premium`), mocked routing visible in UI | Real tiered execution: local Llama-3 70B for `cheap`, GPT-4o only for `premium`; per-team budget caps |
| **Telemetry query** (single PromQL pulls 1M points on high-cardinality services) | 5 fixed PromQL queries; no cardinality control | Force `topk` / `sum by (psm)` reducers; recording-rule precompute; adaptive window shrink (30m → 5m → 1m on timeout) |
| **Trace volume** (Bits ingests billions of spans/min) | Datadog APM page-limit 100 | Sampling-aware API; head-based sampled errors only; never query unsampled |
| **Checkpoint storage** (100k incidents/day = single Postgres saturates) | `SqliteSaver` / `PostgresSaver` | Partitioned by region; TiDB / CockroachDB; TTL + cold-storage archive |
| **Runbook RAG** (10k+ docs across BUs) | In-memory store, TF-IDF / OpenAI fallback | Milvus / Faiss persistent vector store; per-PSM namespace; cross-namespace fallback only when nothing matches |
| **Cardinality / multi-tenancy** | `service` is a free string | Require `PSM + env + cluster` tuple; namespace partitioning per BU |
| **Provider sprawl** | Datadog + Prometheus + Loki | `MegatronProvider` / `ByteLogProvider` / `BitsProvider` — same `DataProvider` ABC, ~300 lines each |
| **Self-observability** | Just `structlog` | Prometheus metrics on every node (latency, error rate, tier-distribution); the agent gets paged when it can't page |
| **Multi-region** | Single deployment | One agent cluster per region; runbook library replicated; checkpointer reads from local replica |

### What's mocked TODAY so you can demo / interview against it

We didn't ship Kafka — but we shipped *the shape of the system you'd
build if you had Kafka*. Specifically:

* **`POST /api/incidents/burst?n=50`** — fires 50 synthetic alerts at
  the dashboard. Watch them queue up against the bounded worker pool
  (`SRE_MAX_CONCURRENT=4` by default) — exactly what would happen
  when a hub service dies in prod and 50 dependent services all alert
  within seconds.
* **`GET /api/scale/stats`** — exposes `queued / active / completed`
  counters + LLM-calls-per-minute. The dashboard's "Scale" strip
  surfaces this live, so you can *see* the queue absorb the burst.
* **Tier classifier** — every incident gets tagged `rule` / `cheap` /
  `premium` based on severity, signal quality, and runbook match.
  Visible as a badge on each incident card. Today the routing is
  cosmetic; tomorrow it points to different model endpoints.
* **Per-tier counters** — `/api/scale/stats` breaks calls down by
  tier so you can answer "what % of incidents would have hit GPT-4o
  in the last hour?" in interviews.

```bash
# Try it
curl -X POST http://localhost:5080/api/incidents/burst?n=50
watch -n1 'curl -s http://localhost:5080/api/scale/stats'
```

---

## Related projects

The architecture patterns (lane discipline, typed evidence, hub-and-spoke,
trust-but-verify) come from the tutorial
[**openclaw-setup-guide**](https://github.com/doraemonlyz-jpg/openclaw-setup-guide) —
which walks through building a multi-agent system from first principles.

---

## License

MIT
