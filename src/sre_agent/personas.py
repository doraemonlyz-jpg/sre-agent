"""
Loads the persona markdown files into Python strings. Each persona becomes
the `system` message of its LangGraph node.

We keep them as standalone .md files instead of inlining the prompts because:
- They're easier to iterate on (open in any editor, render on GitHub)
- Non-engineers can review them
- They double as documentation for the multi-agent design
"""

from __future__ import annotations

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
def load(agent_id: str) -> str:
    """Read the persona markdown by id (e.g. 'incident-pm', 'log-detective')."""
    path = _personas_dir() / f"{agent_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"persona not found: {agent_id} ({path})")
    return path.read_text(encoding="utf-8")
