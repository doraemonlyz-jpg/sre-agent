# SRE Agent System — v1 Design (production)

> **v1 update** — this design is now production-shaped. The orchestration is
> implemented in [LangGraph](https://langchain-ai.github.io/langgraph/), agents
> use real LLMs via a model-agnostic factory, state is checkpointed to Postgres
> for restart-safety, and every node has a rule-based fallback for when the LLM
> is unavailable. See § 11 (Implementation) for the production stack.

> A multi-agent on-call assistant. When an alert fires, the system automatically
> investigates across logs, metrics, traces, and recent deploys, then proposes
> a remediation — **never executes one in v0**.
>
> Designed by reusing every pattern from our `boss-company`:
> Hub-and-spoke orchestration, lane discipline, structural EVIDENCE gates,
> trust-but-verify, and watchdog fallbacks.

---

## 1. Problem we solve

Modern SRE pain (real numbers from public reports):

| Pain | Cost |
|---|---|
| Mean time to detect (MTTD) | 5-15 min (good teams) |
| **Mean time to diagnose (MTTI)** | **30-120 min** (the bottleneck) |
| Mean time to recover (MTTR) | 15-60 min (after diagnosis) |
| Avg cost of a major incident at a $1B SaaS | $300k-$3M per hour |
| 3-AM oncall calls per engineer per quarter | 4-12 |

> **80% of incident time is spent on diagnosis, not on the fix.**
> Diagnosis is the perfect job for AI: it's reading text (logs / traces / commits)
> and pattern matching. That's exactly what LLMs do well.

Our v0 takes a fresh PagerDuty alert and within **60-90 seconds** produces:

1. A ranked list of likely root causes
2. The exact log lines / trace IDs / metrics graphs that support each hypothesis
3. A suggested remediation (rollback / scale / restart / config change)
4. A 1-paragraph summary the oncall can paste into the incident channel

The human still clicks "execute" — but they save ~30 minutes of grep-the-dashboard work.

---

## 2. Why multi-agent (vs. single GPT-4o call)

Single-agent fails because:

| Problem | Why it kills a single Agent |
|---|---|
| 5 data sources (logs / metrics / traces / deploys / topology) | Each has a different API and a different "what to look for" prompt |
| Latency: 60s SLA | 5 sources × 10s each = 50s sequential — too slow without parallelism |
| Different trust levels | Log Detective can read PII; Remediation Suggester must NOT |
| Hallucinated tool calls | Single agent fabricates log lines it never read. Critical in incidents. |
| Different model tiers | Triage = cheap small model; Hypothesis = needs Claude/GPT-4o |

A 5-agent system fixes all 5 by **specialization + parallelism + lane discipline**.

---

## 3. Architecture

```mermaid
flowchart TB
    Alert(["🚨 PagerDuty / Datadog Alert<br/>(webhook)"])
    Dash["🖥️ <b>SRE Dashboard</b><br/>Flask, port 5080"]

    PM(("🎯 <b>Incident PM</b><br/>orchestrator<br/>(gpt-oss:20b)"))

    LD["📜 <b>Log Detective</b><br/>grep / tail / count<br/>(qwen2.5-coder:7b)"]
    MA["📈 <b>Metrics Analyst</b><br/>CPU/mem/latency/error rate<br/>(gpt-oss:20b)"]
    TR["🧬 <b>Trace Reader</b><br/>span hot path<br/>(gpt-oss:20b)"]
    DH["🔀 <b>Deploy Historian</b><br/>recent commits / config<br/>(qwen2.5-coder:7b)"]
    RC["📚 <b>Runbook Consultant</b><br/>retrieves team knowledge<br/>(no LLM — pure RAG)"]

    HG["🧠 <b>Hypothesis Generator</b><br/>aggregate evidence + runbooks<br/>(gpt-oss:20b)"]
    RS["🛠️ <b>Remediation Suggester</b><br/>NEVER executes<br/>cites runbook commands<br/>(gpt-oss:20b)"]

    DD[("📊 Datadog<br/>logs/metrics/APM")]
    GH[("🐙 GitHub<br/>commits/PRs")]
    K8S[("☸️ k8s API<br/>(read-only)")]
    RB[("📚 runbooks/*.md<br/>OpenAI/Ollama/TF-IDF")]

    Report(["📝 <b>Incident Report</b><br/>posted to Slack +<br/>shown in dashboard"])
    Human(["🙋 Oncall<br/>clicks execute"])

    Alert -->|webhook| Dash --> PM
    PM -.parallel.-> LD & MA & TR & DH & RC
    LD <-.queries.-> DD
    MA <-.queries.-> DD
    TR <-.queries.-> DD
    DH <-.queries.-> GH
    DH <-.queries.-> K8S
    RC <-.retrieves.-> RB
    LD & MA & TR & DH & RC -->|typed Evidence| HG
    HG --> RS --> Report --> Human

    classDef ext fill:#3d2155,stroke:#ff4dca,color:#fff
    classDef hub fill:#2a1f4d,stroke:#b84dff,color:#fff
    classDef wkr fill:#1a2342,stroke:#00f0ff,color:#e8edf7
    classDef data fill:#1c3a2a,stroke:#4dffaa,color:#fff
    classDef safe fill:#3a1a1a,stroke:#ff4757,color:#fff
    class Alert,Human,Report ext
    class Dash,PM,HG hub
    class LD,MA,TR,DH,RC wkr
    class DD,GH,K8S,RB data
    class RS safe
```

### Agent roster

| # | Agent | Model | Allowed reads | Allowed writes | Forbidden |
|---|---|---|---|---|---|
| 1 | **Incident PM** | `gpt-oss:20b` | INCIDENT.json | INCIDENT.json, STATUS.json | code, k8s, executing anything |
| 2 | **Log Detective** | `qwen2.5-coder:7b` | Datadog logs API | `LogsEvidence` | metrics, traces |
| 3 | **Metrics Analyst** | `gpt-oss:20b` | Datadog metrics API | `MetricsEvidence` | logs (could be PII) |
| 4 | **Trace Reader** | `gpt-oss:20b` | Datadog APM API | `TracesEvidence` | code |
| 5 | **Deploy Historian** | `qwen2.5-coder:7b` | GitHub API, kubectl get | `DeploysEvidence` | kubectl write |
| 6 | **Runbook Consultant** | _(none — pure retrieval)_ | `runbooks/*.md`, embedding API | `RunbookEvidence` | LLM calls, writing runbooks, live telemetry |
| 7 | **Hypothesis Generator** | `gpt-oss:20b` | all `*Evidence` blocks | `HypothesisList` | data source APIs (no fresh queries) |
| 8 | **Remediation Suggester** | `gpt-oss:20b` | `HypothesisList` + `RunbookEvidence` | `RemediationPlan` | **anything that mutates state** |

**Why the Runbook Consultant has no LLM**:
> Retrieval is deterministic and cheap. Running an LLM here to "summarize" the
> retrieved chunks would just cost tokens and add latency without improving
> signal — the hypothesis generator is already the LLM step that reasons
> over evidence, and it's better served by raw runbook excerpts (which it
> can quote verbatim) than by another LLM's paraphrase. The Consultant
> stays in its lane: it retrieves, it filters by service, it scores. No
> reasoning, no hallucination surface area.

**Why "Remediation Suggester" has zero write access to production**:
> v0 is a **read-only diagnostic**. Action is human-in-the-loop. The agent
> writes a markdown file the human reads. This is the strictest possible
> lane discipline — and it makes the whole system safe to ship to a real
> oncall rotation on day 1.

---

## 4. The EVIDENCE block — our anti-hallucination contract

Every worker reply ends with this structured block. The PM and Hypothesis Generator only trust what's inside it.

```
<EVIDENCE source="datadog-logs">
  <QUERY>service:checkout-api status:error @http.status_code:500 within 30m</QUERY>
  <HITS>1247</HITS>
  <FIRST_AT>2026-05-11T03:42:17Z</FIRST_AT>
  <PEAK_AT>2026-05-11T03:48:00Z</PEAK_AT>
  <TOP_MESSAGE count=983>"ConnectionPoolTimeout: timed out waiting for a connection (pool size: 10)"</TOP_MESSAGE>
  <TOP_MESSAGE count=201>"redis.exceptions.ConnectionError: Error connecting to redis-prod-2.cache.svc"</TOP_MESSAGE>
  <CITATIONS>
    log_id:AwAAAYj... at 03:48:23
    log_id:AwAAAYj... at 03:48:31
  </CITATIONS>
</EVIDENCE>
<RESULT>FOUND</RESULT>
```

**Why this works** (lessons from the boss-company):

- `<HITS>` is a number — the LLM can't fudge it
- `<CITATIONS>` are real Datadog log IDs the PM can re-query
- `<RESULT>FOUND|NO_SIGNAL|ERROR</RESULT>` is the only thing the PM uses to branch
- If a worker replies without an EVIDENCE block → **rejected, retry** (structural gate)

This is exactly the QA `<EXIT=N>` / DevOps `<HTTP=200>` pattern from our boss company.

---

## 5. End-to-end timeline

Goal: **alert in → human-readable diagnosis out in < 90 seconds**.

```mermaid
sequenceDiagram
    autonumber
    participant PD as PagerDuty
    participant D as SRE Dashboard
    participant PM as Incident PM
    participant LD as Log Detective
    participant MA as Metrics Analyst
    participant TR as Trace Reader
    participant DH as Deploy Historian
    participant HG as Hypothesis Generator
    participant RS as Remediation Suggester
    participant Slack as Slack

    PD->>D: webhook (service, severity, time)
    D->>PM: spawn with alert context
    note over PM: T+5s
    PM->>LD: investigate logs (parallel)
    PM->>MA: investigate metrics (parallel)
    PM->>TR: investigate traces (parallel)
    PM->>DH: any recent deploys? (parallel)

    par parallel investigation
        LD-->>PM: EVIDENCE(logs)
    and
        MA-->>PM: EVIDENCE(metrics)
    and
        TR-->>PM: EVIDENCE(traces)
    and
        DH-->>PM: EVIDENCE(deploys)
    end
    note over PM: T+40s (parallel = 4×faster than serial)

    PM->>HG: 4 EVIDENCE blocks, give hypotheses
    HG-->>PM: ranked hypotheses with citations
    note over PM: T+60s

    PM->>RS: top hypothesis, suggest remediation
    RS-->>PM: REMEDIATION.md (no execute)
    note over PM: T+80s

    PM->>D: write INCIDENT.json + Slack post
    D->>Slack: 📣 Incident summary
    note over D: T+90s — done
```

---

## 6. UI — the SRE Dashboard

Reuses the cyberpunk theme from boss-dashboard. Three columns:

```
┌─────────────────────── SRE COMMAND CENTER ──────────────────────┐
│ ALERTS: 3 active │ AGENTS: 6 busy │ MTTI today: 1m 12s ✓        │
├──────────────────┬───────────────────────────┬──────────────────┤
│ ACTIVE ALERTS    │ INCIDENT DETAIL           │ AGENT LIVE LOG   │
│                  │   svc: checkout-api       │ [LD] querying DD │
│ ⚠️ checkout-api  │   severity: SEV-2          │ [LD] 1247 hits  │
│   500 spike      │   started: 03:42 UTC       │ [MA] cpu normal  │
│   ↑ investigating│                            │ [TR] slow span:  │
│                  │ EVIDENCE TABS:             │      redis 8.4s  │
│ ⚠️ search-api    │  [Logs] [Metrics] [Traces] │ [DH] deploy 12m  │
│   p99 latency    │  [Deploys]                 │      ago: PR#4421│
│   ✓ resolved     │                            │ [HG] hypothesis: │
│                  │ HYPOTHESES:                │      redis exhaust│
│ INFO incidents   │  ① Redis pool exhaustion   │ [RS] suggesting  │
│ • payment-api    │     (4 evidence, conf 87%) │      rollback... │
│                  │  ② upstream timeout chain  │                  │
│                  │     (2 evidence, conf 31%) │                  │
│                  │                            │                  │
│                  │ SUGGESTED REMEDIATION:     │                  │
│                  │  ▷ Rollback to v2.3.1      │                  │
│                  │    (deployed 30m before)   │                  │
│                  │  ▷ Verify Redis pool size  │                  │
│                  │  ▷ Scale connection pool   │                  │
│                  │                            │                  │
│                  │ [ POST TO SLACK ]          │                  │
│                  │ [ MARK FALSE POSITIVE ]    │                  │
└──────────────────┴───────────────────────────┴──────────────────┘
```

---

## 7. Roadmap

| Phase | What | When |
|---|---|---|
| **v0** (this session) | Scaffold + personas + dashboard + mock data demo | Tonight |
| **v0.5** | Real Datadog MCP integration (read-only), drop-in for mocks | +1 day |
| **v1** | PagerDuty webhook, Slack integration, persistence | +1 week |
| **v1.5** | Eval golden dataset (10 past real incidents, measure success rate) | +2 weeks |
| **v2** | k8s read-only context, GitHub deploy correlation | +1 month |
| **v3** | Optional auto-remediation (rollback/scale only, with kill-switch) | +3 months |

---

## 8. Success metrics

What we measure to know if it works:

| Metric | Target v0 | Target v1 |
|---|---|---|
| **Diagnosis latency p50** | < 90s | < 60s |
| **Diagnosis latency p95** | < 180s | < 90s |
| **Top hypothesis correct on real incidents** | 50% | 70% |
| **% of incidents where remediation suggestion is useful** | 30% | 60% |
| **False positive rate (alert that wasn't an incident)** | < 20% (we say "no signal") | < 10% |
| **Cost per incident** | < $0.10 (mostly local) | < $0.20 |

**The bar to ship**: 50% top-hypothesis-correct + diagnosis in < 90s. At 50% correct,
oncall already saves time because they don't have to start from zero.

---

## 9. What we are explicitly NOT building

| Won't do | Why |
|---|---|
| Auto-remediation | v0 = trust, v3 maybe. Wrong action in prod is worse than late diagnosis. |
| Anomaly detection from raw metrics | Datadog already does this. We consume their alerts. |
| Generic chat with logs | Honeycomb/Coralogix do this. Our angle is **alert → action**. |
| Multi-tenant SaaS | Single-team internal tool first. SaaS is v3+. |
| Mobile UI | Oncall is at a laptop. |

---

## 10. Open questions (need user input later)

1. **Datadog org**: which one to test against? (need API key for v0.5)
2. **Slack workspace**: where to post incident reports? (need webhook for v1)
3. **PagerDuty service**: which service to wire webhook from? (v1)
4. **Eval data**: any past real Datadog incidents I can replay for the eval suite? (v1.5)

For v0 tonight, we don't need answers to any of these. We use mock alerts + canned Datadog responses.

---

## 11. Implementation (v1, this branch)

The design above is the contract. This section describes how it's actually built.

### 11.1 Orchestration: LangGraph

We picked LangGraph over hand-rolled threading or a chat framework (LangChain agents, CrewAI, AutoGen) because:

- **First-class parallel fan-out** — we can declare "PM has 4 children" and the
  framework runs them concurrently and merges their outputs with a reducer.
- **Stateful checkpointing** — every node transition writes to SQLite/Postgres,
  so an incident survives a pod restart mid-investigation.
- **Conditional edges** — `if hypothesis.confidence < 0.4 → no_signal_path`
  is a one-liner.
- **Mature ecosystem** — `with_structured_output(SomePydanticModel)` is
  built-in and handles the JSON-schema dance.

The graph is defined in `src/sre_agent/graph.py`. It compiles to the same
topology as the diagram in § 3.

### 11.2 Typed I/O: Pydantic

Every agent's input and output is a Pydantic model. Critical examples:

```python
class LogsEvidence(_EvidenceBase):
    source: Literal["datadog-logs"] = "datadog-logs"
    result: EvidenceResult                # enum: FOUND | NO_SIGNAL | ERROR
    hits: int = Field(..., ge=0)          # can't be negative
    citations: list[str] = []             # log IDs the PM can re-verify
    interpretation: str = Field(..., max_length=400)

class RemediationAction(BaseModel):
    title: str
    command: str                          # exact copy-paste shell command
    why: str
    expected_effect: str
    reversal: str                         # REQUIRED — no actions without an undo path
    risk: Literal["LOW", "MEDIUM", "HIGH", "NONE"]
```

The schemas are the structural EVIDENCE-block gate from v0 — but now enforced
by Python's type system instead of regex parsing. `LangChain`'s
`.with_structured_output(Schema)` ensures the LLM returns JSON that fits the
schema; if it doesn't, we retry.

### 11.3 Model factory

```python
get_chat_model(role="orchestrator")  # PM, Hypothesis, Remediation
get_chat_model(role="worker")        # 4 parallel investigators
```

The factory picks a provider in this order:
1. `SRE_LLM_PROVIDER` env var (explicit)
2. `OPENAI_API_KEY` set → OpenAI
3. `ANTHROPIC_API_KEY` set → Anthropic
4. Else → Ollama (local)

Per-role models are tunable independently (`SRE_LLM_ORCHESTRATOR=gpt-4o`,
`SRE_LLM_WORKER=gpt-4o-mini`) so you can spend smart cents per incident.

### 11.4 Graceful degradation

Every node wraps its LLM call in a try/except and falls back to either:

- A rule-based interpretation generated from raw data (for workers)
- A minimal "LLM unavailable, escalating to human" plan (for synthesizers)

The fallback always produces a valid `IncidentReport` with `confidence ≤ 0.30`
so the on-call sees something. The test suite pins LLM at an unreachable URL
and asserts the pipeline still produces a useful report — this is the
**regression gate** for production reliability.

### 11.5 Persistence

| Mode | Backing store | When |
|---|---|---|
| `SRE_CHECKPOINTER=sqlite` (default) | `./.state/checkpoints.db` | local dev, CI |
| `SRE_CHECKPOINTER=postgres` | `$DATABASE_URL` | production |

LangGraph checkpoints after every node. If the dashboard pod crashes between
"Log Detective FOUND" and "Hypothesis Generator", the next pod resumes from
the saved state instead of re-investigating from scratch.

### 11.6 Deployment topology

```
                ┌──────────────────────────┐
                │     ingress / nginx       │
                └──────┬───────────────┬───┘
                       │               │
                       ▼               ▼
                ┌──────────────┐  ┌──────────────┐
                │  gunicorn 1  │  │  gunicorn 2  │   (4 workers × 2 threads)
                │  Flask + LG  │  │  Flask + LG  │
                └──────┬───────┘  └──────┬───────┘
                       │                 │
                       └────────┬────────┘
                                ▼
                       ┌────────────────┐
                       │   Postgres     │   (LangGraph checkpoints + history)
                       └────────────────┘
                                ▲
                                │
                       ┌────────┴────────┐
                       │   OpenAI /      │
                       │   Anthropic /   │
                       │   Ollama        │
                       └─────────────────┘
```

`docker compose up --build` brings this up locally. For real prod, drop the
`Dockerfile` into your container platform of choice (ECS, k8s, Cloud Run) and
point `DATABASE_URL` at a managed Postgres.

### 11.7 What's still v1.1+

The pipeline is production-shaped, but a few seams still point at mocks:

- **DatadogProvider** is a stub — needs real Logs/Metrics/APM API calls
- **PagerDuty webhook** — `/api/incidents/fire` is open today; needs HMAC verification
- **Slack posting** — preview exists; needs the actual `chat.postMessage` call
- **OpenTelemetry** — `structlog` is wired but no spans yet
- **Auth** — none today; v1.1 adds bearer tokens

These are all "swap one provider/integration in" jobs; the agent design and
LangGraph are stable.

