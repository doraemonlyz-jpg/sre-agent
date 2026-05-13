"""
LLM factory.

Why a factory: we want a single line in every node — `get_chat_model("worker")` —
and have it pick:

- A specific model from env (`SRE_LLM_WORKER=gpt-4o-mini`)
- Or fall back to the role default for the active provider
- Or auto-detect provider based on which API key is set

Roles:
- `orchestrator`: needs reasoning + planning (PM, Hypothesis, Remediation)
- `worker`: cheap, fast, tool-friendly (Log Detective, Metrics, Traces, Deploys)

Two reasons for separating them:
- Cost: orchestrator runs once, worker runs 4 times per incident.
- Quality: orchestrator needs to weigh contradictory evidence; workers are mostly
  formatting structured I/O.
"""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

# HarnessCallback both (a) increments the Phase-E counter (in scale.COUNTERS)
# AND (b) records a per-call LLMCallRecord into the harness ring buffer with
# agent / incident / prompt_sha / latency / token-usage / status. One callback
# feeds both observability planes — counter strip and call-trace endpoint.
from sre_agent.harness import HARNESS_CALLBACK

Provider = Literal["openai", "anthropic", "ollama"]


class ModelRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"


# Sensible defaults per (provider, role).
_DEFAULTS: dict[Provider, dict[ModelRole, str]] = {
    "openai":    {ModelRole.ORCHESTRATOR: "gpt-4o",           ModelRole.WORKER: "gpt-4o-mini"},
    "anthropic": {ModelRole.ORCHESTRATOR: "claude-opus-4-1",  ModelRole.WORKER: "claude-haiku-4-5"},
    "ollama":    {ModelRole.ORCHESTRATOR: "gpt-oss:20b",      ModelRole.WORKER: "qwen2.5-coder:7b"},
}


def get_default_provider() -> Provider:
    """
    Pick a provider from env. Order:
    1. SRE_LLM_PROVIDER explicit
    2. OPENAI_API_KEY set → openai
    3. ANTHROPIC_API_KEY set → anthropic
    4. fall back to ollama (assumes localhost:11434 reachable)
    """
    explicit = os.environ.get("SRE_LLM_PROVIDER", "").strip().lower()
    if explicit in {"openai", "anthropic", "ollama"}:
        return explicit  # type: ignore[return-value]

    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "ollama"


def _resolve_model_id(role: ModelRole, provider: Provider) -> str:
    env_key = f"SRE_LLM_{role.value.upper()}"
    return os.environ.get(env_key) or _DEFAULTS[provider][role]


@lru_cache(maxsize=8)
def get_chat_model(role: ModelRole | str, temperature: float = 0.0) -> BaseChatModel:
    """
    Return a LangChain BaseChatModel for the requested role.

    Cached so repeated calls in the same process share one client. We disable
    streaming because every node downstream uses .with_structured_output()
    which doesn't stream anyway.
    """
    if isinstance(role, str):
        role = ModelRole(role)

    provider = get_default_provider()
    model_id = _resolve_model_id(role, provider)

    callbacks = [HARNESS_CALLBACK]

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model_id, temperature=temperature, callbacks=callbacks)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model_id, temperature=temperature, callbacks=callbacks)

    # Ollama (local)
    from langchain_ollama import ChatOllama
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    return ChatOllama(
        model=model_id, temperature=temperature, base_url=base_url, callbacks=callbacks
    )
