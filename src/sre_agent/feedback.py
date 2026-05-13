"""
Feedback persistence — the substrate for the L5 flywheel.

The flywheel:

    incident → agent diagnoses → oncall reviews → feedback captured
              ↘                                                ↗
               this module persists, A/B + drift use it, eval/* uses it
                                  ↘                ↗
                            new prompts, new runbooks

Without persistent feedback, prompt iteration is anecdote. With it,
we can:

  1. Group incidents by `prompt_sha` → see which prompt version
     produced more thumbs-down outcomes.
  2. Auto-mine "we said X, oncall corrected to Y" pairs to seed
     candidate runbook drafts.
  3. Feed labeled examples back into the eval harness (today's
     "what was the right answer" becomes tomorrow's golden case).

This file owns the storage shape. The Flask endpoint in dashboard/app.py
is just a thin shim.

Storage:
  * `~/.sre-agent/feedback/<incident_id>.json`   — one file per record,
    multiple records per incident appended to a `records:` list.
  * Same dir respects SRE_FEEDBACK_DIR env override.
  * Atomic write via tmp + rename. Concurrent appenders use an in-process
    RLock so two oncall submitting at once don't lose a write.

Schema (kept loose so we can evolve without a migration):
  {
    "incident_id": "abc123",
    "records": [
      {
        "id": "fb-...",
        "ts": 1731110400.123,
        "verdict": "thumbs_up" | "thumbs_down" | "correct" | "incorrect",
        "submitter": "oncall@team",           # from auth token or 'anon'
        "rating": 1..5,                        # optional
        "correct_root_cause": "...",           # what was actually wrong
        "correct_remediation": "...",          # what fixed it
        "free_text": "...",
        "prompt_shas_seen": {"hypothesis-gen": "a1b2c3d4", ...},
        "tags": ["false-positive"|"helpful"|...]
      },
      ...
    ]
  }
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

log = logging.getLogger("sre_agent.feedback")


Verdict = Literal["thumbs_up", "thumbs_down", "correct", "incorrect"]
VALID_VERDICTS = ("thumbs_up", "thumbs_down", "correct", "incorrect")


@dataclass
class FeedbackRecord:
    id: str
    ts: float
    verdict: Verdict
    submitter: str = "anon"
    rating: int | None = None
    correct_root_cause: str | None = None
    correct_remediation: str | None = None
    free_text: str | None = None
    # Snapshot of what the agent claimed as the root cause at report
    # time. Stored on the feedback record (not just derived from the
    # incident) so post-hoc analyses still work after incidents roll.
    agent_root_cause: str | None = None
    prompt_shas_seen: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _feedback_dir() -> Path:
    raw = os.environ.get("SRE_FEEDBACK_DIR")
    p = Path(raw).expanduser() if raw else Path.home() / ".sre-agent" / "feedback"
    p.mkdir(parents=True, exist_ok=True)
    return p


class FeedbackStore:
    """JSON-on-disk feedback store, append-only per incident."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: dict[str, int] = {v: 0 for v in VALID_VERDICTS}
        self._totals_loaded = False

    # ── write ────────────────────────────────────────────────────────

    def append(
        self,
        incident_id: str,
        rec: FeedbackRecord,
        *,
        alert: dict[str, Any] | None = None,
    ) -> None:
        """
        Append a feedback record for `incident_id`.

        `alert` is an optional snapshot of the alert that produced the
        incident, written once per blob the first time we see it. We
        store it because the in-memory INCIDENTS dict rolls — without
        a persisted copy, post-hoc analyses (e.g. auto-runbook drafter)
        lose the service/description context that's needed for
        clustering corrections.
        """
        path = _feedback_dir() / f"{incident_id}.json"
        with self._lock:
            if path.is_file():
                try:
                    blob = json.loads(path.read_text("utf-8"))
                except Exception:
                    log.exception("feedback.read_corrupt %s", path)
                    blob = {"incident_id": incident_id, "records": []}
            else:
                blob = {"incident_id": incident_id, "records": []}

            blob["records"].append(rec.to_json())
            blob["updated_at"] = time.time()
            if alert and "alert" not in blob:
                blob["alert"] = alert

            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(blob, ensure_ascii=False, indent=2), "utf-8")
            tmp.replace(path)

            self._counters[rec.verdict] = self._counters.get(rec.verdict, 0) + 1

    # ── read ─────────────────────────────────────────────────────────

    def get(self, incident_id: str) -> dict[str, Any] | None:
        path = _feedback_dir() / f"{incident_id}.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text("utf-8"))
        except Exception:
            log.exception("feedback.read_failed %s", path)
            return None

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Most recently updated feedback files first."""
        d = _feedback_dir()
        files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        out = []
        for p in files[:limit]:
            try:
                out.append(json.loads(p.read_text("utf-8")))
            except Exception:
                continue
        return out

    def summary(self) -> dict[str, Any]:
        """Aggregate counts. Lazily loads totals from disk once per process."""
        with self._lock:
            if not self._totals_loaded:
                self._reload_totals_locked()
                self._totals_loaded = True
            counters = dict(self._counters)
        pos = counters.get("thumbs_up", 0) + counters.get("correct", 0)
        neg = counters.get("thumbs_down", 0) + counters.get("incorrect", 0)
        total = pos + neg
        return {
            "counters": counters,
            "positive": pos,
            "negative": neg,
            "total": total,
            "csat": round(pos / total, 3) if total else None,
        }

    def _reload_totals_locked(self) -> None:
        self._counters = {v: 0 for v in VALID_VERDICTS}
        d = _feedback_dir()
        for p in d.glob("*.json"):
            try:
                blob = json.loads(p.read_text("utf-8"))
            except Exception:
                continue
            for r in blob.get("records", []):
                v = r.get("verdict")
                if v in self._counters:
                    self._counters[v] += 1

    def reset(self) -> None:
        """Test hook — wipes the in-memory counters AND on-disk files."""
        with self._lock:
            self._counters = {v: 0 for v in VALID_VERDICTS}
            self._totals_loaded = True
            d = _feedback_dir()
            for p in d.glob("*.json"):
                with contextlib.suppress(OSError):
                    p.unlink()


STORE = FeedbackStore()


# ──────────────────────────────────────────────────────────────────────────
# Construction helpers
# ──────────────────────────────────────────────────────────────────────────


def make_record(
    *,
    verdict: str,
    submitter: str = "anon",
    rating: int | None = None,
    correct_root_cause: str | None = None,
    correct_remediation: str | None = None,
    free_text: str | None = None,
    agent_root_cause: str | None = None,
    prompt_shas_seen: dict[str, str] | None = None,
    tags: list[str] | None = None,
) -> FeedbackRecord:
    if verdict not in VALID_VERDICTS:
        raise ValueError(
            f"verdict must be one of {VALID_VERDICTS}, got {verdict!r}"
        )
    if rating is not None and not (1 <= rating <= 5):
        raise ValueError("rating must be in 1..5")
    return FeedbackRecord(
        id="fb-" + uuid.uuid4().hex[:10],
        ts=time.time(),
        verdict=verdict,  # type: ignore[arg-type]
        submitter=submitter,
        rating=rating,
        correct_root_cause=correct_root_cause,
        correct_remediation=correct_remediation,
        free_text=free_text,
        agent_root_cause=agent_root_cause,
        prompt_shas_seen=prompt_shas_seen or {},
        tags=tags or [],
    )
