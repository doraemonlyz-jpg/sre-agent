"""LLM factory — picks a provider based on env, returns a LangChain Runnable."""

from __future__ import annotations

from sre_agent.models.factory import (
    ModelRole,
    get_chat_model,
    get_default_provider,
)

__all__ = ["ModelRole", "get_chat_model", "get_default_provider"]
