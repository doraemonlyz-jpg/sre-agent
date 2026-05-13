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
