"""
Loads the persona markdown files into Python strings. Each persona becomes
the `system` message of its LangGraph node.

We keep them as standalone .md files instead of inlining the prompts because:
- They're easier to iterate on (open in any editor, render on GitHub)
- Non-engineers can review them
- They double as documentation for the multi-agent design

**Prompt fingerprinting (harness L4 prerequisite)**

`load_with_sha(agent_id)` returns `(text, sha8)` where `sha8` is a stable
short hash of the persona content. Every agent records its prompt_sha into
the harness ring buffer when it invokes the LLM, so we can later answer:

  * "Incident #123 was diagnosed using which version of the hypothesis
    prompt?" — point at the record's prompt_sha, compare to current.
  * "After we tweaked log-detective.md last Tuesday, did accuracy drop?"
    — group records by prompt_sha, plot accuracy delta.

Without fingerprinting, post-hoc analysis of prompt churn is impossible.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path


def _personas_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "personas"
        if candidate.is_dir() and (candidate / "incident-pm.md").exists():
            return candidate
    raise FileNotFoundError("personas/ directory not found in any parent of " + str(here))


@lru_cache(maxsize=16)
def _read(agent_id: str) -> tuple[str, str]:
    """Read the persona markdown by id, returning (text, sha8)."""
    path = _personas_dir() / f"{agent_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"persona not found: {agent_id} ({path})")
    text = path.read_text(encoding="utf-8")
    sha8 = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return text, sha8


def load(agent_id: str) -> str:
    """Read the persona markdown by id. Kept for backward compatibility."""
    return _read(agent_id)[0]


def load_with_sha(agent_id: str) -> tuple[str, str]:
    """
    Like `load()` but returns `(text, sha8)`.

    Use this in agent nodes so the harness recorder can tag every LLM call
    with the exact prompt version that produced it.
    """
    return _read(agent_id)
