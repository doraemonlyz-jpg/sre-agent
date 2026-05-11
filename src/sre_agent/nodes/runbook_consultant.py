"""
Runbook Consultant node — the team's institutional memory.

Pure retrieval: deterministic, no LLM call. The hypothesis generator and
remediation suggester are the ones that *reason* over the retrieved
chunks; we just surface the most relevant ones.

Design decisions:

* No LLM here. The chunks are LLM-friendly markdown already; an extra
  LLM call to "summarize" them would just cost tokens and add latency
  without improving signal.
* Service filter is binding. If alert.service is set, chunks tagged to
  a *different* service are excluded. Chunks with no service tag are
  always eligible (they're cross-cutting general guidance).
* Soft failure. If retrieval errors out — embedding backend down, files
  unreadable, whatever — we return an empty RunbookEvidence with
  result=ERROR rather than crashing the graph.
"""

from __future__ import annotations

from typing import Any

from sre_agent.logging import get_logger
from sre_agent.nodes._helpers import make_event
from sre_agent.runbooks import get_store
from sre_agent.schemas import (
    EvidenceResult,
    GraphState,
    RunbookEvidence,
    RunbookHit,
)

log = get_logger("runbook_consultant")


# How many chunks to retrieve. Three is the sweet spot for LLM context —
# more dilutes the top match's signal, fewer misses the case where the
# correct chunk is #2 or #3.
_K = 3


def _build_query(alert: Any) -> str:
    """Concatenate the alert fields that carry semantic signal."""
    parts: list[str] = [alert.service, alert.description]
    parts.extend(alert.tags or [])
    return " ".join(p for p in parts if p)


def runbook_consultant(state: GraphState) -> dict[str, Any]:
    alert = state["alert"]
    log.info("runbook_consultant.start", service=alert.service)

    try:
        store = get_store()
    except Exception as e:
        log.exception("runbook_consultant.store_load_failed", error=str(e))
        ev = RunbookEvidence(
            result=EvidenceResult.ERROR,
            library_size=0,
            backend="none",
            interpretation=f"could not load runbook library: {e}",
        )
        return _emit(ev)

    if store.size == 0:
        ev = RunbookEvidence(
            result=EvidenceResult.NO_SIGNAL,
            library_size=0,
            backend=store.backend.name,
            interpretation="runbook library is empty",
        )
        return _emit(ev)

    query = _build_query(alert)
    try:
        results = store.search(query, service=alert.service, k=_K)
    except Exception as e:
        log.exception("runbook_consultant.search_failed", error=str(e))
        ev = RunbookEvidence(
            result=EvidenceResult.ERROR,
            library_size=store.size,
            backend=store.backend.name,
            interpretation=f"retrieval failed: {e}",
        )
        return _emit(ev)

    if not results:
        ev = RunbookEvidence(
            result=EvidenceResult.NO_SIGNAL,
            library_size=store.size,
            backend=store.backend.name,
            interpretation=(
                f"no matching runbook chunks for {alert.service!r} "
                f"(library has {store.size} chunk(s))"
            ),
        )
        return _emit(ev)

    hits = [
        RunbookHit(
            path=r.chunk.path,
            title=r.chunk.title,
            service=r.chunk.service,
            tags=r.chunk.tags,
            score=round(r.score, 3),
            snippet=r.chunk.to_snippet(),
        )
        for r in results
    ]
    top = hits[0]
    interpretation = (
        f"top match: '{top.title}' from {top.path} "
        f"(score={top.score:.2f}); {len(hits)} relevant chunk(s) retrieved"
    )

    ev = RunbookEvidence(
        result=EvidenceResult.FOUND,
        hits=hits,
        library_size=store.size,
        backend=store.backend.name,
        citations=[f"runbook:{h.path}#{h.title}" for h in hits],
        interpretation=interpretation,
    )
    return _emit(ev)


def _emit(ev: RunbookEvidence) -> dict[str, Any]:
    """Package the evidence into the partial state update LangGraph expects."""
    detail = ev.interpretation
    if ev.hits:
        detail = f"{len(ev.hits)} runbook chunk(s) matched — top: {ev.hits[0].title}"
    return {
        "runbooks": ev,
        "events": [
            make_event(
                "runbook-consultant",
                "evidence",
                detail,
                result=ev.result.value,
                backend=ev.backend,
                library_size=ev.library_size,
            )
        ],
    }
