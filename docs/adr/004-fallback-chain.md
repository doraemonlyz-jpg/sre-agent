# ADR-004: 3-tier LLM fallback chain

- **Status:** Accepted
- **Date:** 2026-04-30

## Context

The agent's value proposition collapses if the LLM is unreachable.
A real on-call user does not want to see "OpenAI returned 503" at
3am -- they want a degraded but usable diagnosis.

We have three plausible model "tiers" available in production:

1. A premium provider (OpenAI / Anthropic) -- best quality.
2. A locally-hosted Ollama model -- free, slower, lower quality.
3. A pure-Python rule-based responder -- no LLM, just templated
   output from the rule-based fallback in `hypothesis_gen`.

## Decision

Build a `FallbackChainModel` (`src/sre_agent/models/fallback.py`)
that wraps the three tiers behind the same `BaseChatModel` interface
LangGraph already calls. Each tier has its own per-call timeout. On
timeout or exception, the chain transparently falls down to the next
tier and records the transition for observability.

Enable with `SRE_LLM_FALLBACK=on`. The factory
(`src/sre_agent/models/factory.py:get_chat_model`) returns a
`FallbackChainModel` when the env is set; otherwise the historical
single-model behaviour.

Per-tier metrics:

- `sre_llm_fallback_total{from_tier, to_tier}`
- `sre_llm_calls_total{tier, status}` (already existed; we propagate
  the `tier` label down through the chain)

## Considered

- **Just retry on the same provider.** Already done at the call level
  (`src/sre_agent/retry.py`). Doesn't help when the provider has a
  multi-minute outage -- that's exactly when fallbacks pay off.
- **Round-robin across providers.** Hard to budget cost, harder to
  debug. A strict tier ordering matches "use the best model that's
  responsive RIGHT NOW".
- **Skip the rule-based degraded tier; just return ERROR.** Rejected
  because the rule-based tier already exists in `hypothesis_gen` --
  exposing it as a model lets the rest of the graph keep its hands
  clean and produces a real (if low-confidence) hypothesis.

## Consequences

- **Good:** the whole graph keeps running through any single-tier
  outage. The dashboard shows a banner ("LLM degraded -- responses
  may be lower quality") sourced from the same metric.
- **Good:** per-tier timeouts mean a wedged premium provider doesn't
  block the call -- we move to local Ollama quickly.
- **Bad:** the rule-based tier's confidence is hard-capped at 0.30.
  `finalize` then routes to `no_signal`, which is correct (we shouldn't
  claim a confident diagnosis from templated text) but means oncall
  must read the event stream rather than the headline phase. Documented
  in `docs/index.html` Section 13.
- **Bad:** more code paths to test. We have ~15 fallback-specific
  unit tests in `tests/test_fallback.py` covering each transition.
