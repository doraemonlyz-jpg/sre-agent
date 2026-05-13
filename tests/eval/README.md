# Eval harness (L4)

What's in this folder:

```
tests/eval/
├── __init__.py
├── README.md             ← this file
├── scoring.py            ← pure functions: score one report vs expected
├── runner.py             ← loads YAML cases + runs the graph + applies scoring
├── cases/                ← golden incident library (YAML, one file per case)
│   ├── redis-pool-exhaustion.yaml
│   ├── deploy-bad-config.yaml
│   └── false-positive-noisy-rule.yaml
└── (tests/test_eval.py runs the whole thing as pytest)
```

## Why this exists

Without an eval harness, "we shipped a better prompt" is wishful thinking.
Every prompt edit is a regression risk: a tweak that lifts case A might tank
case B. The harness solves that with three things:

1. **Golden cases** — for each well-known failure pattern in our seeded
   scenarios, a YAML file pins down what the *correct* output looks like
   (phase, cited evidence, hypothesis keywords, runbook reference,
   confidence range, action types).

2. **Pure scoring** — `scoring.py` takes one `IncidentReport` (or the dict
   that the dashboard stores) and one `ExpectedOutcome`, returns a 0–1
   score and a list of `pass/fail` reasons. No globals, no I/O.

3. **A pytest hook** — `tests/test_eval.py` (gated behind `-m eval`)
   runs the graph for each case and asserts `score >= threshold`.
   In CI, a prompt diff that drops mean accuracy below 0.8 fails the
   build. Locally, you run `pytest -m eval -v` and read the per-case
   breakdown.

## Running it

```bash
# Default: full test suite skips eval (it's slow).
pytest

# Just the eval, with detailed per-case breakdown.
pytest -m eval -v

# Single case (faster iteration).
pytest -m eval -v -k redis-pool

# Eval against real Ollama instead of the offline fallback.
SRE_LLM_PROVIDER=ollama OLLAMA_BASE_URL=http://localhost:11434 \
    pytest -m eval -v --no-header
```

## How a case is scored

Each check below is `1.0` if it passes, `0.0` otherwise. The case's score
is the mean across all defined checks. The PASS threshold is `0.8` (any
case can fail one cheap check and still pass).

| Field                          | Meaning                                                                |
|--------------------------------|------------------------------------------------------------------------|
| `expected.phase`               | Final phase must be in this set (e.g. `[diagnosed, no_signal]`).       |
| `expected.must_cite_evidence`  | Every name in this list must appear in `hypothesis.supporting_evidence`. |
| `expected.hypothesis_keywords_any` | At least one of these strings (case-insensitive) appears in `top.title` or `top.detail`. |
| `expected.runbook_path_contains`   | `runbooks` evidence cites a runbook whose path contains this string.   |
| `expected.confidence_range`    | Top hypothesis confidence falls within `[lo, hi]`.                     |
| `expected.remediation_action_titles_any` | At least one action title contains one of these keywords.     |
| `expected.must_not_phase`      | The final phase must NOT be in this set.                               |

All fields are optional — leave one out, it isn't scored. Start each case
with the 2-3 dimensions that matter most for that incident.

## When to add a case

  * After diagnosing a new failure pattern in prod, distill it into a
    case here. Future prompt changes will be measured against it
    forever (or until you delete the case explicitly).

  * After a postmortem where the agent gave a wrong answer, add the
    case with the *correct* expected outcome. This is the regression
    test for that miss.

  * After a customer asks "why did your AI say X for incident #123",
    add a case captured from that incident.

## Limitations

  * The scoring is keyword/structural, not semantic. "Redis connection
    pool exhausted" and "out of Redis connections" are different
    keywords. Either list both as alternatives or accept that the
    score is approximate. The point is regression detection, not
    leaderboards.

  * Cases run against `MockProvider` by default — deterministic but
    artificial. For real-world eval, swap in canned recordings from
    Datadog / Prometheus (one future TODO is a `ReplayProvider`).

  * Without a live LLM the graph hits its rule-based fallback for
    most cases. That's intentional: the fallback path is a critical
    safety net and *should* pass its own minimum bar. Cases that
    require LLM reasoning are tagged `requires_llm: true` so you can
    skip them when offline.
