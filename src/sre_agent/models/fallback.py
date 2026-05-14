"""
sre_agent.models.fallback -- B4 multi-model fallback chains.

Why this exists
---------------
A single LLM in the critical path is a single point of failure. The
observed failure modes we want to survive:

  * **Provider outage**: OpenAI / Anthropic API returns 503 for 5
    minutes. The whole pipeline shouldn't go dark.
  * **Tail latency**: gpt-oss:20b on a cold Ollama process takes 90s
    for the first call. Beyond our 90s diagnosis budget.
  * **Rate limiting**: a noisy neighbour exhausted the org's TPM.
  * **Quality regression**: a model upgrade silently broke the
    structured-output contract for a few hours.

The mitigation is a **graceful fallback chain** per agent role:

  premium model  ->  cheaper / faster model  ->  rule-based responder

Each transition is recorded as both a harness LLMCallRecord (so post-
mortems show "the diagnosis used the cheap model because premium
timed out") AND a Prometheus counter (so we can alarm on
`rate(sre_llm_fallbacks_total[5m]) > 0.5`).

Boot-safety
-----------
The chain is built lazily and each tier is constructed only when
needed. If a tier's constructor fails (e.g. ChatOllama can't reach
localhost), we skip it transparently and move on. A chain with zero
viable tiers raises explicitly at first .invoke() -- not at import --
so the dashboard can still start in a degraded-but-introspectable
state.
"""

from __future__ import annotations

import concurrent.futures
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel

from sre_agent.harness import RECORDER, LLMCallRecord

log = logging.getLogger("sre_agent.models.fallback")


# ──────────────────────────────────────────────────────────────────────────
# Rule-based responder (the last-resort tier)
# ──────────────────────────────────────────────────────────────────────────


class RuleBasedDegradedModel:
    """
    A 0-latency, schema-valid degraded responder. Deliberately NOT a
    `BaseChatModel` subclass -- we only need the surface our chain
    actually uses (`invoke`, `with_structured_output`). Avoiding the
    LangChain Pydantic v2 inheritance keeps construction cheap and the
    code easier to reason about.

    Tradeoffs:
      - The response is intentionally low-confidence and conservative.
      - For hypothesis-gen, returns "evidence insufficient, page senior
        oncall" -- which is what a human SRE says when they have zero
        LLM available.

    The tier is identified by `tier_name` (set on construction) so the
    harness and Prometheus counters can label it correctly.
    """

    def __init__(self, tier_name: str = "rule") -> None:
        self.tier_name = tier_name

    @property
    def name(self) -> str:
        return self.tier_name

    def invoke(self, _input: Any, **_kwargs: Any) -> Any:
        from langchain_core.messages import AIMessage
        return AIMessage(
            content=(
                "DEGRADED MODE: every LLM tier failed for this agent. "
                "Returning a conservative null-output so the pipeline can "
                "complete. Recommend paging senior oncall."
            ),
        )

    def with_structured_output(self, schema: Any, **_kwargs: Any) -> "_RuleBasedStructured":
        return _RuleBasedStructured(schema)


@dataclass
class _RuleBasedStructured:
    schema: Any

    def invoke(self, _input: Any, **_kwargs: Any) -> Any:
        return _build_degraded_instance(self.schema)


def _build_degraded_instance(schema: Any) -> Any:
    """
    Construct a minimally-valid instance of a Pydantic model with
    "degraded mode" sentinel values where possible.

    Strategy: walk the model's fields; for each, supply a degraded
    default that's either schema-permissive (None / "" / []) or an
    explicit sentinel string. We do best-effort and fall back to the
    schema's own defaults for any field we can't shape ourselves.
    """
    if not hasattr(schema, "model_fields"):
        # Not a Pydantic model -- give up gracefully.
        return None

    args: dict[str, Any] = {}
    for fname, finfo in schema.model_fields.items():
        ann = finfo.annotation
        # Container / scalar shape heuristics
        if ann is str or getattr(ann, "__origin__", None) is None and ann == str:
            args[fname] = "DEGRADED"
        elif ann is int or ann == int:
            args[fname] = 0
        elif ann is float or ann == float:
            args[fname] = 0.0
        elif ann is bool:
            args[fname] = False
        elif getattr(ann, "__origin__", None) is list:
            args[fname] = []
        elif getattr(ann, "__origin__", None) is dict:
            args[fname] = {}
        else:
            # Keep it simple: try the default if present, else None.
            if finfo.default is not None and finfo.default is not Ellipsis:
                args[fname] = finfo.default
            else:
                args[fname] = None

    try:
        return schema(**args)
    except Exception:
        # If schema validation is too strict for our placeholder, return
        # the raw dict -- the caller's downstream handling will treat
        # this as a degraded result.
        return args


# ──────────────────────────────────────────────────────────────────────────
# Fallback chain
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class Tier:
    """One step in the fallback chain."""

    name: str  # "premium" | "cheap" | "rule" -- low-cardinality label for metrics
    builder: Callable[[], BaseChatModel]  # lazy: avoids constructing all tiers eagerly
    timeout_seconds: float | None = 30.0  # None = no timeout

    _built: BaseChatModel | None = None

    def model(self) -> BaseChatModel:
        if self._built is None:
            self._built = self.builder()
        return self._built


class FallbackChainModel:
    """
    A BaseChatModel-compatible wrapper that invokes a sequence of tiers
    until one succeeds. Each transition is recorded.

    NOT a subclass of BaseChatModel on purpose: we don't want LangChain
    to recursively call back into our callbacks. We implement only the
    surface that node code actually uses (`invoke` and
    `with_structured_output`), and proxy everything else to the active
    tier via __getattr__.
    """

    def __init__(self, agent: str, tiers: list[Tier]) -> None:
        if not tiers:
            raise ValueError("fallback chain needs at least one tier")
        self.agent = agent
        self.tiers = tiers
        self._structured_schema: Any = None

    # ── single-tier invocation with timeout enforcement ──────────────

    def _call_tier(self, tier: Tier, input_: Any, **kwargs: Any) -> Any:
        model = tier.model()
        if self._structured_schema is not None:
            model = model.with_structured_output(self._structured_schema)  # type: ignore[assignment]

        if tier.timeout_seconds is None:
            return model.invoke(input_, **kwargs)

        # Enforce timeout in a worker thread. We don't share a pool
        # because the typical invocation count is small and per-call
        # threads keep the code simple. Real prod with high QPS should
        # use a shared executor.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(model.invoke, input_, **kwargs)
            try:
                return future.result(timeout=tier.timeout_seconds)
            except concurrent.futures.TimeoutError as e:
                future.cancel()  # best-effort cancellation
                raise TimeoutError(
                    f"tier {tier.name!r} exceeded {tier.timeout_seconds}s"
                ) from e

    # ── public API ───────────────────────────────────────────────────

    def invoke(self, input_: Any, **kwargs: Any) -> Any:
        """Try each tier in order. On exception or timeout, record the
        fallback transition and try the next tier."""
        last_exc: BaseException | None = None
        for i, tier in enumerate(self.tiers):
            t0 = time.perf_counter()
            try:
                result = self._call_tier(tier, input_, **kwargs)
                if i > 0:
                    # We succeeded on a non-primary tier. Note that we
                    # already recorded the FALLBACK transition into this
                    # tier on the previous iteration's failure.
                    log.info(
                        "fallback.recovered agent=%s tier=%s elapsed_ms=%d",
                        self.agent, tier.name, int((time.perf_counter() - t0) * 1000),
                    )
                return result
            except Exception as e:
                last_exc = e
                # Identify the fallback we're about to do.
                reason = (
                    "timeout" if isinstance(e, TimeoutError)
                    else type(e).__name__.lower()
                )
                if i + 1 < len(self.tiers):
                    next_tier = self.tiers[i + 1]
                    self._record_transition(
                        from_tier=tier.name, to_tier=next_tier.name, reason=reason,
                        error=str(e)[:200],
                    )
                else:
                    log.error(
                        "fallback.exhausted agent=%s last_tier=%s reason=%s",
                        self.agent, tier.name, reason,
                    )
        # All tiers exhausted.
        raise last_exc if last_exc else RuntimeError(
            f"fallback chain for {self.agent} exhausted with no exception"
        )

    def with_structured_output(self, schema: Any, **_kwargs: Any) -> "FallbackChainModel":
        """Returns a chain that applies `with_structured_output(schema)`
        to each tier just before invocation. We can't pre-apply because
        LangChain returns wrapper Runnables that we'd then have to
        track separately."""
        cloned = FallbackChainModel(self.agent, self.tiers)
        cloned._structured_schema = schema
        return cloned

    # ── helpers ──────────────────────────────────────────────────────

    def _record_transition(
        self,
        *,
        from_tier: str,
        to_tier: str,
        reason: str,
        error: str,
    ) -> None:
        # Harness: a typed record so post-mortems show the chain.
        try:
            import uuid

            RECORDER.record(LLMCallRecord(
                id=uuid.uuid4().hex[:12],
                kind="fallback",
                ts=time.time(),
                agent=self.agent,
                detail={
                    "from_tier": from_tier,
                    "to_tier": to_tier,
                    "reason": reason,
                    "error": error,
                },
                status="degraded",
            ))
        except Exception:
            pass
        # Prometheus: counter for alarming on fallback rate.
        try:
            from sre_agent import metrics as _m
            _m.record_fallback(
                agent=self.agent, from_tier=from_tier, to_tier=to_tier, reason=reason,
            )
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────
# Public builders
# ──────────────────────────────────────────────────────────────────────────


def build_default_chain(
    agent: str,
    *,
    role: str = "worker",
    primary_timeout_s: float = 30.0,
    cheap_timeout_s: float = 20.0,
    include_rule_based: bool = True,
) -> FallbackChainModel:
    """
    Construct a 3-tier chain: configured-provider -> ollama-local ->
    rule-based degraded responder.

    The primary tier is whatever the existing factory picks (respects
    SRE_LLM_PROVIDER + role defaults). The secondary tier is always
    local Ollama so we have a non-cloud fallback when the network is
    the problem. The tertiary tier is the rule-based responder.

    Pass `include_rule_based=False` for tests that want to assert on
    real-error propagation.
    """
    from sre_agent.models.factory import (
        ModelRole,
        get_chat_model,
        get_default_provider,
    )

    def _build_primary() -> BaseChatModel:
        return get_chat_model(ModelRole(role))

    def _build_local_ollama() -> BaseChatModel:
        # Lazy import; ollama may not be installed in CI.
        from langchain_ollama import ChatOllama
        import os
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        model_id = (
            "qwen2.5-coder:7b" if role == "worker" else "gpt-oss:20b"
        )
        return ChatOllama(model=model_id, temperature=0.0, base_url=base_url)

    tiers: list[Tier] = [
        Tier("primary", _build_primary, timeout_seconds=primary_timeout_s),
    ]
    # Don't duplicate local-ollama if the primary IS already ollama.
    if get_default_provider() != "ollama":
        tiers.append(Tier("cheap", _build_local_ollama, timeout_seconds=cheap_timeout_s))
    if include_rule_based:
        tiers.append(Tier("rule", RuleBasedDegradedModel, timeout_seconds=None))

    return FallbackChainModel(agent=agent, tiers=tiers)


def build_chain_from_factory_funcs(
    agent: str,
    tiers: list[tuple[str, Callable[[], BaseChatModel], float | None]],
) -> FallbackChainModel:
    """
    Explicit-builder variant used by tests and advanced callers.

    Each element is `(tier_name, builder, timeout_seconds)`.
    """
    return FallbackChainModel(
        agent=agent,
        tiers=[Tier(name, builder, timeout) for name, builder, timeout in tiers],
    )
