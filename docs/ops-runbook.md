# SRE Agent — Production Operations Runbook

This document tells you everything you need to know to operate the agent
in production. It is written for the oncall, not for the developer.

## 1. The 30-second mental model

The SRE agent is a Flask process. It receives alerts on `POST /api/incidents/fire`
(direct) or `POST /api/alerts/webhook` (Datadog / PagerDuty / generic).
For each alert it spawns a LangGraph pipeline that calls 7 agents in
parallel-then-sequence and writes a structured `IncidentReport`.

Failures degrade gracefully — rule-based fallbacks fire when the LLM
times out, and the response cache eats duplicate alerts. The system
*never* hangs forever waiting on the LLM.

```
alert  →  webhook  →  rate-limit  →  auth  →  cache lookup
                                                    ├── HIT  →  return cached report (~0ms)
                                                    └── MISS →  worker pool (max N)
                                                                  └── LangGraph (7 agents)
                                                                        └── feedback persists
                                                                        └── harness records
                                                                        └── observability ships
```

## 2. Required env

| Var | Default | Required in prod |
|---|---|---|
| `SRE_AUTH_REQUIRED` | `0` (off) | **yes** — flip to `1` |
| `SRE_AUTH_TOKENS_FILE` | — | **yes** — `/etc/sre-agent/tokens.json` |
| `SRE_RATE_LIMIT` | `on` | leave on |
| `SRE_MAX_CONCURRENT` | `4` | tune to your LLM rate budget |
| `SRE_CHECKPOINTER` | `sqlite` | `postgres` for multi-replica |
| `SRE_STATE_DIR` | `~/.sre-agent` | a mounted volume |
| `SRE_FEEDBACK_DIR` | `~/.sre-agent/feedback` | a mounted volume |
| `OLLAMA_BASE_URL` *or* `OPENAI_API_KEY` *or* `ANTHROPIC_API_KEY` | — | at least one |
| `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` | — | recommended |
| `SLACK_WEBHOOK_URL` | — | if posting to Slack |
| `SLACK_SIGNING_SECRET` | — | if Slack interactive buttons |
| `SRE_SLACK_VERIFY_REQUIRED` | `0` | **yes** when SLACK_SIGNING_SECRET is set |

## 3. Minting + rotating tokens

```bash
# Mint a token offline (one-shot)
python -c "
from sre_agent.auth import mint_token
import json
t = mint_token('oncall-prod', ['read','fire','feedback'], note='primary oncall')
print(json.dumps({
  'name': t.name, 'secret': t.secret, 'scopes': list(t.scopes), 'note': t.note,
}, indent=2))
" >> /etc/sre-agent/tokens.json
```

Token file shape (a JSON array):

```json
[
  {"name": "oncall-prod",   "secret": "...",  "scopes": ["read","fire","feedback"]},
  {"name": "alerts-webhook","secret": "...",  "scopes": ["fire"]},
  {"name": "root",          "secret": "...",  "scopes": ["admin"]}
]
```

Rotation: edit the file, save, wait < 60s. The registry reloads lazily
without a process restart. Old tokens stop working as soon as the file
is rewritten.

Scope guide:

* `read` — `/api/incidents`, `/api/harness/*`, `/api/feedback/summary`
* `fire` — `/api/incidents/fire`
* `burst` — `/api/incidents/burst` (much more dangerous than `fire`)
* `feedback` — `POST /api/incidents/<id>/feedback`
* `admin` — wildcard, includes future scopes

## 4. k8s probes

```yaml
livenessProbe:
  httpGet: { path: /api/health, port: 5080 }
  periodSeconds: 10
  timeoutSeconds: 1
  failureThreshold: 3

readinessProbe:
  httpGet: { path: /api/readiness, port: 5080 }
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 6     # 30s of failures pulls pod out of mesh
```

The deep readiness probe verifies:

1. LangGraph compiled (catches import-time breakage).
2. Checkpointer dir exists and is writable.
3. Provider (Datadog / Prometheus / Loki / Mock) is reachable.
4. Runbook store is loaded (returns `degraded: true` if RAG is down,
   doesn't fail readiness — RAG is opportunistic).

## 5. Burning questions during an incident

### "Why isn't the agent picking up alerts?"

1. `curl /api/readiness` — what's degraded?
2. `curl /api/harness/summary` — is the queue full? Is the rate limiter
   rejecting? Are LLM calls erroring?
3. `tail -f $SRE_STATE_DIR/agent.log` — look for `auth.token_rejected`
   (token file wrong), `rate limit exceeded`, or `llm.error`.

### "Why is diagnosis quality dropping?"

1. `pytest -m eval` — does the offline eval still pass?
2. `sre-agent eval-drift` — what's the drift vs baseline?
3. `/api/harness/calls?kind=llm_call&limit=200` — group by `prompt_sha`;
   look for a new SHA with elevated `status=error` rate. Roll back
   that variant: `unset SRE_PROMPT_AB_<AGENT>`.
4. `/api/feedback/summary` — CSAT trend.

### "The dashboard says CACHE on every incident"

That's working as designed. Same alert fired twice within
`SRE_CACHE_TTL_SECONDS` (default 300s) returns the previous incident's
diagnosis with `served_from_cache=true`. If the alert is *legitimately*
different but digit-normalization is collapsing it, lower TTL:
`export SRE_CACHE_TTL_SECONDS=60` and restart.

### "Slack buttons aren't working"

1. `curl -X POST $BASE/api/slack/actions -d 'payload=junk'` — should
   400 `'payload' is not JSON`. If you get 401 instead, signing is
   required but `SLACK_SIGNING_SECRET` is wrong.
2. Slack app config → Interactivity → Request URL must be
   `https://your-host/api/slack/actions` (not the webhook URL).
3. Slack timestamp drift: the HMAC check has a 5-minute replay window.
   If your clock is off you'll see silent 401s.

## 6. Pinning a prompt rollback

If a prompt change goes bad:

```bash
# Hard-pin every hypothesis-gen call to the conservative variant
export SRE_PROMPT_VARIANT_HYPOTHESIS_GEN=conservative
systemctl restart sre-agent

# Or — if you want only the next 1% of traffic on conservative while you
# investigate
export SRE_PROMPT_AB_HYPOTHESIS_GEN=conservative:0.01
```

Verify the rollback landed: `/api/prompts/variants` shows the active
pin / A/B state for every agent.

## 7. Tuning rate limit + worker pool together

Three numbers compose:

```
inbound RPS         ≤  SRE_RATE_FIRE.rate     (per caller)
LLM concurrency     =  SRE_MAX_CONCURRENT     (process-wide)
LLM tier mix        =  classify_tier()         (rule / cheap / premium %)
```

Rough sizing for one replica + Llama-3 70B locally:

* `SRE_RATE_FIRE=20:40` (20 alerts/sec sustained, burst 40)
* `SRE_MAX_CONCURRENT=4` (Llama-3 70B at ~6s p50 → ~40 incidents/min)
* `SRE_CACHE_TTL_SECONDS=300` (5x effective throughput with repeats)

If you're getting 429s on legitimate traffic, raise the rate; if your
LLM provider starts erroring with 429s of its own, lower
`SRE_MAX_CONCURRENT`.

## 8. Drift-detection CI wiring

Add to `.github/workflows/eval.yml`:

```yaml
- name: eval offline (every PR)
  run: pytest -m eval

- name: drift detection (nightly)
  if: github.event_name == 'schedule'
  env:
    SRE_EVAL_REQUIRES_LLM: '1'
    OLLAMA_BASE_URL: ${{ secrets.OLLAMA_URL }}
  run: |
    sre-agent eval-drift --threshold 0.05 --json | tee drift-report.json

- name: alert if drifted
  if: failure()
  run: ./scripts/post-to-slack.sh drift-report.json
```

The baseline lives in `tests/eval/baseline.json`. Refresh it after an
intentional prompt change:

```bash
sre-agent eval-drift --update-baseline --require-llm
git add tests/eval/baseline.json
git commit -m "eval: refresh baseline after prompt update on <agent>"
```

## 9. Backup + restore

What lives on disk:

| Path | What | Lose it = lose |
|---|---|---|
| `$SRE_STATE_DIR/state/` | LangGraph checkpoints (per `thread_id`) | mid-flight incidents cannot resume |
| `$SRE_FEEDBACK_DIR/` | Per-incident feedback JSON | the flywheel signal |
| `tests/eval/baseline.json` | The eval baseline | drift detection is gone until you re-baseline |
| `personas/` + `personas/variants/` | All prompts | nothing — they're in git |
| `runbooks/` | Markdown runbooks for RAG | rebuild RAG from the markdown |

Daily backup target (1 line cron):

```bash
0 3 * * *  rsync -aR /var/lib/sre-agent/{state,feedback} /backup/$(date -u +%F)/
```

## 10. Useful one-liners

```bash
# How many LLM calls in the last buffer window? Which agent dominates?
curl -s :5080/api/harness/calls | jq '
  [.records[] | select(.kind=="llm_call") | .agent] | group_by(.) |
  map({agent: .[0], n: length}) | sort_by(-.n)'

# CSAT this week
curl -s :5080/api/feedback/summary | jq '{csat,total,positive,negative}'

# Active A/B
curl -s :5080/api/prompts/variants | jq '.agents | map(select(.pinned or .ab))'

# Recent 5xx in the rate limiter (shouldn't exist; 429 is fine)
curl -s :5080/api/harness/summary | jq '.rate_limit'

# Force a cache eviction (admin token required)
# (Not exposed via API yet; flip SRE_CACHE_TTL_SECONDS=1 and wait 1s.)
```

---

If anything in this document is wrong, fix it. The whole point of this
agent is that we keep the runbooks honest.

---

## 11. L6 — running the flywheel jobs

L6 turns the feedback corpus into actionable improvements. Both jobs are
**offline batch**, safe to run from a cron, and read-only against the
on-disk feedback store. Neither auto-merges anything; both emit
Markdown that goes through normal code review.

### 11.1 Winner promotion

What it does: groups feedback by `(agent, prompt_sha)`, runs a
two-proportion z-test per agent, and recommends a variant for
promotion when (sample size ≥ 50/arm, point delta ≥ 3pp, p < 0.05,
candidate is NOT the current baseline).

Recommended schedule: **daily at 02:00 UTC**, after the previous day's
feedback has flushed.

```bash
sre-agent winner \
  --baselines "hypothesis-gen=$(cat /etc/sre-agent/baselines/hypothesis-gen.sha)" \
  --out-md /var/lib/sre-agent/reports/winner-$(date -u +%Y%m%d).md \
  --out-json /var/lib/sre-agent/reports/winner-$(date -u +%Y%m%d).json \
  --promote-exit-code 0
```

If you want the cron to **fail loudly** when a promotion is recommended
(so it shows up in the on-call's PagerDuty / Slack), set
`--promote-exit-code 1`. The job exits non-zero and your job scheduler
notifies — that's the prompt for someone to open the Markdown and
write a PR.

How to actually promote (manual, deliberate):

```bash
# 1. Inspect the report
cat /var/lib/sre-agent/reports/winner-2026-01-15.md

# 2. Copy the variant prompt over the baseline
cp personas/variants/hypothesis-gen-conservative.md personas/hypothesis-gen.md

# 3. Commit + redeploy. The next harness record's prompt_sha will
#    naturally roll to the new value.
git commit personas/hypothesis-gen.md -m "promote conservative variant (+7.7pp, p=0.0004)"
```

If the prod data is bad (e.g. there was a flood of false positives on
one day that skewed verdicts): nothing happens automatically. The cron
keeps emitting reports; you keep ignoring them until the verdict
stabilises. The system is **suspicious by default** — false promotion
is much worse than slow promotion.

### 11.2 Auto-runbook drafter

What it does: walks every `thumbs_down` / `incorrect` feedback record
that has a `correct_root_cause`, clusters them by `(service,
alert-shape)`, and emits a draft runbook entry per cluster that
crosses `--min-occurrences`.

Recommended schedule: **weekly on Monday at 06:00 UTC**.

```bash
sre-agent autorunbook \
  --min-occurrences 5 \
  --out-md /var/lib/sre-agent/reports/autorunbook-$(date -u +%Y%W).md
```

Output is **never** auto-committed. Process:
1. Cron writes the Markdown.
2. A separate bot (Slack/GitHub) posts the file to the runbook-review
   channel.
3. Owner of each cluster (= owner of the `service` field) reviews,
   edits the prose into a proper runbook, opens a PR adding it under
   `runbooks/`.
4. Next time the same alert fires, the runbook RAG retrieves it →
   `runbook_consultant` node cites it → cycle closed.

### 11.3 Synthetic data (DO NOT enable in prod)

The seeder is `src/sre_agent/seed.py` and is exposed via
`sre-agent seed --n N` and `SRE_SEED_ON_BOOT=N`.

**Never** set `SRE_SEED_ON_BOOT` on the prod dashboard. It pollutes
the feedback store with fabricated records that the winner cron will
treat as real, and your CSAT graph will start lying to you.

The seeder is for: local dev, interview demos, CI smoke tests, and
populating staging environments that don't yet have organic traffic.

A safe production guardrail (recommended in your deployment manifest):

```yaml
# k8s deployment.yaml
env:
  - name: SRE_SEED_ON_BOOT          # explicitly empty — refuse to seed
    value: ""
```

If you ever see `seeding N synthetic incidents` in the prod dashboard
log on startup, that's a critical config bug; rotate the pod
immediately, clear the feedback dir, and audit the deploy config.

## 12. L6.3 - Confidence calibration

The calibrator maps raw LLM-output confidence to a probability that
*actually means what it says*. Without it, the agent saying "I'm 90%
sure" is right only ~65% of the time and an oncall who trusts the
number runs the wrong runbook.

### 12.1 What it is

- A small JSON file (`data/calibrator.json` by default) containing a
  list of `(raw, calibrated)` breakpoints.
- Loaded once at dashboard boot via `SRE_CALIBRATOR_PATH`.
- Applied transparently to every `hypothesis.confidence` value the
  dashboard surfaces. The raw value is preserved in
  `hypothesis.confidence_raw` so you can audit what the calibrator did.

### 12.2 Fitting it

```bash
# Reads $SRE_FEEDBACK_DIR (or ~/.sre-agent/feedback), writes the artifact.
sre-agent calibrate \
  --out data/calibrator.json \
  --out-md reports/calibration.md

# Inspect what's currently loaded.
sre-agent calibrate-show

# Verify what the live dashboard is applying.
curl http://localhost:5080/api/harness/calibration | jq
```

The fitter uses Pool-Adjacent-Violators isotonic regression -- a
shape-free monotonic estimator that handles the typical "flat in the
middle, sharp at the extremes" LLM miscalibration without assuming a
specific S-curve.

If the feedback corpus has fewer than `--min-pairs` (default 100) pairs
with usable `(agent_confidence, verdict)`, the fitter ships the
**identity calibrator** rather than overfitting noise. The dashboard
falls back to identity on missing/corrupt artifacts too: a broken
calibrator never silently swallows alerts.

### 12.3 Recommended cadence

- **Refit weekly.** Confidence calibration drifts as the underlying
  model versions update, prompts get promoted, and traffic mix changes.
- **Refit after promoting a prompt variant.** The promoted prompt's
  confidence distribution may differ from baseline's.
- **Always refit on a held-out window**, never on the same data you're
  evaluating. The CLI takes a `--feedback-dir` override for this.

### 12.4 Health metrics to watch

- **ECE (Expected Calibration Error)**: target < 0.05. Above 0.10
  means the surfaced confidence is genuinely misleading.
- **Brier score**: target < 0.25. Combines calibration and refinement;
  large jumps week-over-week usually indicate a prompt regression.
- **Number of breakpoints**: 2-15 is typical. A single-breakpoint fit
  means the corpus has very little confidence signal -- check that
  `agent_confidence` is actually being persisted on feedback records.

### 12.5 Failure modes

- **Identity calibrator in prod after `sre-agent calibrate`**: usually
  means feedback records lack `agent_confidence`. Check that the
  dashboard build is L6.3-or-later; pre-L6.3 records have no confidence
  number to fit on.
- **Calibrator pushes high-confidence predictions UP** (worse, not
  better): symptom of a noisy training tail. Run with `--n-bins 20` to
  see the diagram, and consider raising `--min-pairs`.
- **ECE goes up between refits**: prompt promotion drift. The newly
  promoted variant has a different confidence distribution than its
  predecessor; the old calibrator is mis-applied. Refit immediately.

---

## 13. Prometheus metrics + alerting (B1)

The dashboard exposes a `/metrics` endpoint in Prometheus text format.
All names are prefixed `sre_` and follow the upstream naming guide.

### 13.1 The metric surface area

  * **Counters**
    * `sre_incidents_total{result}` — per-phase incident count
    * `sre_llm_calls_total{agent,model,status}` — LLM RPS by status
    * `sre_llm_tokens_total{agent,direction}` — token cost driver
    * `sre_llm_fallbacks_total{agent,from_tier,to_tier,reason}` — B4
    * `sre_cache_events_total{kind}` — `hit` / `miss` / `store` / `evict`
    * `sre_feedback_total{verdict}` — oncall sentiment over time
    * `sre_rate_limit_drops_total{scope}` — L5 rejections
    * `sre_runbook_search_total{backend,hit}` — RAG hit rate

  * **Histograms** (p50 / p95 / p99 buckets baked in)
    * `sre_incident_duration_seconds{result}`
    * `sre_llm_latency_seconds{agent,model}`
    * `sre_runbook_search_latency_seconds{backend}`

  * **Gauges**
    * `sre_calibrator_ece` / `sre_calibrator_brier` / `sre_calibrator_n_train`
    * `sre_active_incidents`
    * `sre_build_info{version,checkpointer,llm_provider}` (constant `1`)

### 13.2 Scrape config

```yaml
scrape_configs:
  - job_name: sre-agent
    scrape_interval: 15s
    static_configs:
      - targets: ['sre-agent-dashboard:5080']
```

The route is unauthenticated by convention; expose it on a private
network or behind a sidecar.

### 13.3 Recommended alert rules

```yaml
groups:
  - name: sre-agent
    rules:
      # Quality alert -- the calibrator drifted.
      - alert: SREAgentCalibratorDrift
        expr: sre_calibrator_ece > 0.10
        for: 6h
        labels: { severity: warning }
        annotations:
          summary: "SRE Agent calibrator ECE > 0.10 for 6h — refit recommended"

      # Reliability alert -- LLM tier-1 is failing a lot.
      - alert: SREAgentExcessFallbacks
        expr: rate(sre_llm_fallbacks_total[5m]) > 0.5
        for: 10m
        labels: { severity: critical }
        annotations:
          summary: "More than 0.5 fallback transitions/sec — primary LLM degraded"

      # Latency alert -- p95 diagnosis breaching 90s SLA.
      - alert: SREAgentDiagnosisSlow
        expr: |
          histogram_quantile(0.95, rate(sre_incident_duration_seconds_bucket[5m])) > 90
        for: 15m
        labels: { severity: warning }
```

---

## 14. LLM fallback chains (B4)

Enable with `SRE_LLM_FALLBACK=on`. Every `get_chat_model()` call returns
a `FallbackChainModel` that proxies `.invoke()` / `.with_structured_output()`
through a chain.

### 14.1 Default chain

For both `orchestrator` and `worker` roles:

```
primary (configured provider, 30s timeout)
  ↓ on timeout / error / rate_limit
cheap (local Ollama, 20s timeout)
  ↓ on timeout / error
rule-based (0-latency degraded responder, no timeout)
```

When the primary IS Ollama, the cheap tier is skipped (no duplicate).

### 14.2 Observing transitions

Every transition writes:

  * `LLMCallRecord(kind="fallback", agent=..., detail={from_tier, to_tier, reason})`
    — visible in `/api/harness/calls`.
  * `sre_llm_fallbacks_total{...}` — Prometheus counter.

### 14.3 Failure modes

- **Rule-based tier serving real traffic**: an SLA-level failure. The
  rule tier is the last-line safety net; if you're seeing
  `to_tier="rule"` increments, your primary AND your local Ollama are
  both unhealthy. Page primary-LLM owner immediately.
- **Spurious fallbacks under load**: if `reason="timeout"` ticks up
  during traffic spikes only, the primary tier's timeout is too
  aggressive. Tune `primary_timeout_s` in `build_default_chain()` or
  scale your primary.

---

## 15. BM25 runbook RAG + persistent index (C1)

### 15.1 Building the index

```bash
sre-agent runbook-index --output data/runbook-index.json --backend bm25
export SRE_RUNBOOK_INDEX_PATH=$(pwd)/data/runbook-index.json
```

Backends:

  * `bm25`     — Lucene-default BM25, zero deps, **recommended**
  * `keyword`  — TF-IDF cosine fallback, kept for tests
  * `openai`   — `text-embedding-3-small` via langchain-openai (network)
  * `ollama`   — `nomic-embed-text` via langchain-ollama (local)
  * `auto`     — tries openai → ollama → bm25

### 15.2 When to rebuild

Whenever any file under `runbooks/` changes. Recommended CI step:

```yaml
- name: Rebuild runbook RAG index
  run: |
    sre-agent runbook-index --output data/runbook-index.json --backend bm25
    git diff --quiet data/runbook-index.json || echo "::error::index drift -- commit data/runbook-index.json"
```

### 15.3 Health metrics

Watch `sre_runbook_search_total{hit="true"}` / `{hit="false"}`. A
hit-rate below 50% means either:

  1. Runbooks are stale (agents are asking questions you don't have
     answers for) — extend the library.
  2. Backend mismatch — you've changed `SRE_EMBEDDINGS_BACKEND` but
     `SRE_RUNBOOK_INDEX_PATH` still points at the old artifact. Rebuild.

---

## 16. Calibration auto-PR cron (B2)

The third L6 cron, alongside `harness-winner` and `harness-autorunbook`.
Lives at `.github/workflows/harness-calibration.yml`. Same template
and CODEOWNERS pattern as the other two:

  * **Schedule**: weekly, Sunday 04:00 UTC.
  * **Threshold**: PR only when new ECE beats live ECE by ≥`CAL_DELTA_THRESHOLD`
    (default 0.03, i.e. 3 percentage points).
  * **Body**: rendered from `PULL_REQUEST_TEMPLATE.md`; the
    `Auto-refit calibrator` checkbox is pre-ticked; the bot's
    statistical report is dropped inside the `<!-- bot-report -->`
    markers.

Manual one-off run (mirrors what the cron does):

```bash
SEED_N=3000 SEED_RNG=42 SEED_AB=0.3 \
  CAL_OUT_PATH=data/calibrator.json \
  CAL_CURRENT_PATH=data/calibrator.json \
  CAL_DELTA_THRESHOLD=0.03 \
  REPORTS_DIR=./reports \
  python scripts/run-calibration-job.py
```

Decision logic:

  * `propose=true`  → calibrator written + PR opened with the report.
  * `propose=false` → report still uploaded as a GitHub artifact for
    audit. We never silently skip.

---

## 17. Real backends (D1) — Prometheus + Loki provider operations

Both providers now share the same hardened HTTP path
(`src/sre_agent/providers/_http.py`):

| Capability | Knob |
| --- | --- |
| Bearer token | `PROMETHEUS_BEARER_TOKEN` / `LOKI_BEARER_TOKEN` |
| Basic auth | `PROMETHEUS_BASIC_AUTH_USER` + `_PASSWORD` (same for `LOKI_*`) |
| Per-call timeout | `PROMETHEUS_HTTP_TIMEOUT_S` / `LOKI_HTTP_TIMEOUT_S` (default 10) |
| Retry attempts | hard-coded 3, full-jitter exponential backoff (0.2s → 5s ceiling) |
| Retried statuses | 429, 500, 502, 503, 504, plus `TimeoutException` / `NetworkError` / `RemoteProtocolError` |

### Health probes

`/api/readiness` calls `provider.health()` for every wired provider.
The probe hits `/-/healthy` (Prometheus) or `/ready` (Loki) with a
2-second timeout and **does not retry** — a wedged backend should
fail fast in the readiness endpoint, not after 30 seconds of retries.

### Self-metrics to dashboard

```text
sre_provider_requests_total{provider="prometheus", outcome="ok"}        12384
sre_provider_requests_total{provider="prometheus", outcome="retry_503"}    18
sre_provider_requests_total{provider="loki",       outcome="ok"}         9012
sre_provider_request_latency_seconds_bucket{provider="prometheus", le="0.5"} 12100
```

### Suggested alert rules

```yaml
- alert: SreProviderHighErrorRate
  expr: sum by (provider) (rate(sre_provider_requests_total{outcome!~"ok|retry_.*"}[5m]))
        / sum by (provider) (rate(sre_provider_requests_total[5m])) > 0.05
  for: 10m
  labels: { severity: warning }
  annotations:
    summary: "{{ $labels.provider }} provider errors > 5% over 10m"

- alert: SreProviderUnhealthy
  expr: probe_success{job="sre-readiness", provider!=""} == 0
  for: 3m
  labels: { severity: critical }
```

---

## 18. PagerDuty paging (D4)

The notifier lives at `src/sre_agent/notifications/pagerduty.py`.
Three lifecycle events: `trigger`, `acknowledge`, `resolve`. Each
posts to PagerDuty's Events API v2 (`/v2/enqueue`) with a stable
`dedup_key` (the agent's `incident_id`).

### Configuration

| Env | Effect |
| --- | --- |
| `PAGERDUTY_ROUTING_KEY` | Integration key from a PD service. Without this the notifier is dry-run. |
| `PAGERDUTY_API_URL` | Override (default `https://events.pagerduty.com`). Useful for sandbox accounts. |
| `PAGERDUTY_HTTP_TIMEOUT_S` | Per-request timeout. Default 5. |
| `PAGERDUTY_MIN_SEVERITY` | `SEV-1` / `SEV-2` / `SEV-3` / `SEV-4`. Default `SEV-2`. |
| `SRE_PAGERDUTY_DRY_RUN` | `true` → never POST; build the payload and return it. |
| `SRE_PAGERDUTY_AUTO_PAGE` | `on` → auto-trigger when the diagnosis pipeline finishes a SEV-1/2 with `phase=diagnosed`. |
| `SRE_DASHBOARD_PUBLIC_URL` | Used in `custom_details.dashboard_url`. |

### Self-metrics

```text
sre_pagerduty_events_total{event_type="trigger",     severity="SEV-1", outcome="ok"}      12
sre_pagerduty_events_total{event_type="trigger",     severity="SEV-1", outcome="dry_run"} 4
sre_pagerduty_events_total{event_type="resolve",     severity="N/A",   outcome="ok"}       9
sre_pagerduty_events_total{event_type="trigger",     severity="SEV-2", outcome="http_500"} 1
```

### Common operations

```bash
# Manually page oncall for a known incident:
curl -XPOST http://localhost:5080/api/incidents/INC-2026...../page

# Resolve when on-call closes the incident:
curl -XPOST http://localhost:5080/api/incidents/INC-2026...../resolve-page
```

### Suggested alert rules

```yaml
- alert: SrePagerDutyDeliveryFailures
  expr: rate(sre_pagerduty_events_total{outcome!~"ok|dry_run|below.*"}[15m]) > 0
  for: 15m
  labels: { severity: critical }
  annotations:
    summary: "PagerDuty notifier failing — incidents not paging"

- alert: SrePagerDutyAllDryRun
  # If you've configured a routing key but EVERY trigger is dry_run,
  # the env var probably isn't reaching the dashboard process.
  expr: increase(sre_pagerduty_events_total{event_type="trigger",outcome="dry_run"}[1h]) > 0
        and on() absent(sre_pagerduty_events_total{event_type="trigger",outcome!="dry_run"})
  for: 1h
  labels: { severity: warning }
```

---

## 19. Self-consistency ensemble (G2)

`SRE_HYPOTHESIS_ENSEMBLE_K` controls the ensemble size for
`hypothesis_generator`:

  * **K=1** (default) — single LLM call. Original behaviour, no
    thread-pool overhead.
  * **K=3** — 3 parallel calls, pick the highest-confidence answer.
    Adds ~1× the latency of the slowest call (not 3×) plus ~10ms
    of thread overhead.
  * **K up to 5** — diminishing returns; more cost for marginal
    accuracy gains. We cap at 5 to defend against typos.

### Self-metrics

```text
sre_ensemble_runs_total{agent="hypothesis-gen", k="3", outcome="ok"}        220
sre_ensemble_runs_total{agent="hypothesis-gen", k="3", outcome="partial"}     8
sre_ensemble_runs_total{agent="hypothesis-gen", k="3", outcome="all_failed"}  1
sre_ensemble_latency_seconds_bucket{agent="hypothesis-gen", le="5"}          200
sre_ensemble_agreement_bucket{agent="hypothesis-gen", le="0.67"}              45
```

### Reading agreement

`sre_ensemble_agreement` is the fraction of ensemble members landing
on the same root-cause bucket (first 40 chars of the hypothesis
title, lowercased). Steady-state expectations:

  * **0.9+** — ensemble is consistent; the model's answer is stable.
  * **0.5–0.8** — model is split. The picker still chooses the most
    confident, but the disagreement is signal that the case is hard.
  * **< 0.4** — every member found something different. Treat the
    output as low-confidence regardless of the displayed score.

### Suggested alert rules

```yaml
- alert: SreEnsembleAllFailing
  expr: rate(sre_ensemble_runs_total{outcome="all_failed"}[15m]) > 0
  for: 15m
  labels: { severity: critical }
  annotations:
    summary: "Every ensemble member failing — LLM upstream is wedged"

- alert: SreEnsembleConsistentlyDivergent
  expr: histogram_quantile(0.5, rate(sre_ensemble_agreement_bucket[1h])) < 0.5
  for: 1h
  labels: { severity: warning }
  annotations:
    summary: "Ensemble agreement p50 below 0.5 — model is consistently split"
```

---

## 20. Golden eval suite operations (E1)

The suite lives under `tests/eval/cases/` (10 YAML cases as of this
release) and the mock scenarios at `mocks/scenarios.json`. Run the
harness three ways:

```bash
# Offline (CI default) — only the 3 fallback-friendly cases run;
# 7 LLM-gated cases skip cleanly.
pytest tests/test_eval.py -m eval

# Online — point at a real LLM and run all 10.
SRE_EVAL_REQUIRES_LLM=1 OLLAMA_BASE_URL=http://localhost:11434 \
  pytest tests/test_eval.py -m eval

# Drift gate — for cron / pre-merge checks.
sre-agent eval-drift                       # exits 1 if mean score dropped > 5%
sre-agent eval-drift --update-baseline     # after intentional prompt changes
```

The baseline JSON (`tests/eval/baseline.json`) is checked in; updating
it requires a PR review (it's effectively the "we agree this score is
acceptable" contract).
