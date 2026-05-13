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
the harness ring buffer when it invokes the LLM.

**Prompt A/B (harness L5)**

`personas/variants/<agent_id>-<variant_name>.md` is treated as an
alternative for `<agent_id>`. Routing is:

  1. `SRE_PROMPT_VARIANT_<agent_id_upper_snake>=<variant_name>` — pin
     every call to that variant. Used in evals and during incident
     replay.
  2. `SRE_PROMPT_AB_<agent_id_upper_snake>=<variant_name>:<frac>` —
     randomly route `<frac>` (0..1) of calls to `<variant_name>`,
     the rest to the baseline. Used for gradual rollout.
  3. Otherwise: baseline.

The harness recorder receives the SHA of the *actually loaded* prompt, so
the A/B assignment is observable end-to-end: filter `/api/harness/calls`
by `prompt_sha` to see how the variant performed.
"""

from __future__ import annotations

import hashlib
import os
import random
from functools import lru_cache
from pathlib import Path


def _personas_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "personas"
        if candidate.is_dir() and (candidate / "incident-pm.md").exists():
            return candidate
    raise FileNotFoundError("personas/ directory not found in any parent of " + str(here))


def _variants_dir() -> Path:
    return _personas_dir() / "variants"


@lru_cache(maxsize=32)
def _read_file(path_str: str) -> tuple[str, str]:
    text = Path(path_str).read_text(encoding="utf-8")
    sha8 = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return text, sha8


def _baseline_path(agent_id: str) -> Path:
    return _personas_dir() / f"{agent_id}.md"


def _variant_path(agent_id: str, variant_name: str) -> Path:
    return _variants_dir() / f"{agent_id}-{variant_name}.md"


def _env_key(agent_id: str, prefix: str) -> str:
    return prefix + agent_id.upper().replace("-", "_")


def _pick_variant(agent_id: str) -> str | None:
    """
    Return the variant_name to use, or None for baseline.

    Order:
      * SRE_PROMPT_VARIANT_<AGENT> — pinned
      * SRE_PROMPT_AB_<AGENT>=name:frac — random
    """
    pinned = os.environ.get(_env_key(agent_id, "SRE_PROMPT_VARIANT_"))
    if pinned:
        return pinned.strip() or None

    ab = os.environ.get(_env_key(agent_id, "SRE_PROMPT_AB_"))
    if not ab:
        return None
    if ":" not in ab:
        return None
    name, frac_str = ab.split(":", 1)
    try:
        frac = float(frac_str)
    except ValueError:
        return None
    if random.random() < max(0.0, min(1.0, frac)):
        return name.strip() or None
    return None


def list_variants(agent_id: str) -> list[str]:
    """All `<agent_id>-<variant>.md` files in the variants dir."""
    d = _variants_dir()
    if not d.is_dir():
        return []
    prefix = f"{agent_id}-"
    return sorted(
        p.stem[len(prefix):]
        for p in d.glob(f"{prefix}*.md")
    )


@lru_cache(maxsize=32)
def _read(agent_id: str) -> tuple[str, str]:
    """Read the BASELINE persona markdown by id, returning (text, sha8)."""
    path = _baseline_path(agent_id)
    if not path.exists():
        raise FileNotFoundError(f"persona not found: {agent_id} ({path})")
    return _read_file(str(path))


def load(agent_id: str) -> str:
    """Read the baseline persona markdown by id. Kept for backward compatibility."""
    return _read(agent_id)[0]


def load_with_sha(agent_id: str) -> tuple[str, str]:
    """
    Return `(text, sha8)` for the persona that should be used for this
    invocation. Resolves any A/B routing first.

    Use this in agent nodes so the harness recorder can tag every LLM call
    with the exact prompt version that produced it.
    """
    variant = _pick_variant(agent_id)
    if variant:
        vpath = _variant_path(agent_id, variant)
        if vpath.is_file():
            return _read_file(str(vpath))
        # Variant requested but missing — fall through to baseline. We
        # don't raise: a missing variant should NEVER take down prod, but
        # we *do* log the miss (caller can wire to harness if needed).
    return _read(agent_id)


def load_specific(agent_id: str, variant_name: str | None = None) -> tuple[str, str]:
    """
    Explicitly load a named variant (or baseline if `variant_name=None`).
    Used by the eval harness to test a candidate prompt without changing
    process-level env state.
    """
    if variant_name is None:
        return _read(agent_id)
    vpath = _variant_path(agent_id, variant_name)
    if not vpath.is_file():
        raise FileNotFoundError(
            f"variant not found: {agent_id}-{variant_name} ({vpath})"
        )
    return _read_file(str(vpath))
