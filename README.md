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
python dashboard/app.py     # http://127.0.0.1:5060
```

### Option B — Docker (production-shaped, with Postgres)

```bash
cp .env.example .env       # add OPENAI_API_KEY or leave blank for Ollama
docker compose up --build  # dashboard at http://localhost:5060
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

---

## Architecture

```
                ┌──────────────┐
                │ incident_pm  │   open incident
                └──────┬───────┘
                       │
            ┌──────────┼──────────┐──────────────┐
            ▼          ▼          ▼              ▼
       log_detec  metrics_an  trace_rdr    deploy_hist     (parallel)
            │          │          │              │
            └──────────┴──────────┴──────────────┘
                       │
                       ▼
              ┌──────────────────┐
              │ hypothesis_gen   │   rank root causes
              └─────────┬────────┘
                        ▼
              ┌──────────────────┐
              │ remediation_sug  │   suggest fix (never executes)
              └─────────┬────────┘
                        ▼
              ┌──────────────────┐
              │     finalize     │   write IncidentReport
              └──────────────────┘
                        ▼
                       END
```

Each node is a small Python function that:

1. Reads typed state from `GraphState` (TypedDict)
2. Optionally calls a `DataProvider` (mock / Datadog)
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
│   │   ├── hypothesis_gen.py
│   │   └── remediation_sug.py
│   ├── providers/
│   │   ├── base.py           # DataProvider ABC
│   │   ├── mock.py           # uses mocks/scenarios.json
│   │   └── datadog.py        # stub for real Datadog (v1.1)
│   ├── models/factory.py     # Ollama / OpenAI / Anthropic factory
│   ├── personas.py           # loads personas/*.md as system prompts
│   ├── logging.py            # structlog setup
│   └── cli.py                # `sre-agent ...` Typer CLI
├── personas/                 # 7 agent personas (markdown, used as system prompts)
├── mocks/scenarios.json      # 3 demo incidents
├── dashboard/                # Flask UI; backend just spawns LangGraph runs
├── tests/                    # pytest, 30 cases, fully offline
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
| `SRE_DASHBOARD_PORT` | `5060` | the Flask UI port |

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

## Tests

```bash
pytest                       # 30 cases, no network, runs in ~20s
pytest --cov=sre_agent       # coverage report
```

The test suite **does not call any real LLM**. Every test pins the LLM factory
to an unreachable Ollama URL and asserts that the graph still produces a valid
`IncidentReport`. This is the regression gate for our "graceful degradation"
property.

---

## What's still TODO (v1.1+)

- [ ] Real Datadog provider (Logs API v2, Metrics v1, APM v2)
- [ ] PagerDuty webhook receiver (`POST /api/webhooks/pagerduty`)
- [ ] Slack posting with action buttons
- [ ] OpenTelemetry tracing on every node
- [ ] Auth: bearer token + per-team isolation
- [ ] Eval suite: 10 hand-labeled historical incidents, accuracy ≥ 80%

---

## Related projects

The architecture patterns (lane discipline, typed evidence, hub-and-spoke,
trust-but-verify) come from the tutorial
[**openclaw-setup-guide**](https://github.com/doraemonlyz-jpg/openclaw-setup-guide) —
which walks through building a multi-agent system from first principles.

---

## License

MIT
