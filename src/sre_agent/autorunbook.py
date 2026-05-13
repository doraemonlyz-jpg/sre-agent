"""
L6.1 -- Auto-runbook drafter.

The richest signal in the feedback corpus isn't the thumbs-up; it's the
thumbs-down where the oncall ALSO took the time to write what the right
answer was. That's free institutional knowledge being typed into a
text field, and right now it just sits there.

This module turns that text into draft runbook entries. The output is
intentionally a `draft_runbook.md` review document -- not an automatic
merge -- because:

  * Oncall corrections are noisy. One person calling memory pressure
    "OOM" and another calling it "leak in v23" should be merged by a
    human, not by string matching.
  * Runbooks are read by humans first, LLMs second. Writing prose
    needs intent the seeder can't fabricate.
  * The whole point of this loop is to AMPLIFY oncall judgement, not
    replace it.

How drafts are formed
---------------------
1. Pull every feedback record where verdict ∈ {thumbs_down, incorrect}
   AND `correct_root_cause` is set.
2. Group by (service, alert-shape-key), where alert-shape-key is a
   crude bucket from the incident's alert description (first few
   meaningful tokens, lowercased). This produces clusters like:
     ("checkout-api", "p99-latency-spiking")
     ("payments-gateway", "5xx-rate-after-deploy")
3. For each cluster with ≥ MIN_OCCURRENCES distinct submitters, emit a
   draft runbook section.
4. The draft section includes:
     * Service + alert pattern.
     * Frequency + first/last seen.
     * The set of "the agent said X but the right answer is Y" pairs.
     * Suggested remediations (from `correct_remediation` field).

The output Markdown is suitable for `git apply`-ing as a new runbook
under `runbooks/auto/` and reviewing in PR.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sre_agent.feedback import STORE as FEEDBACK_STORE

# Lower bound for cluster occurrence count. Below this we suppress --
# one-off corrections aren't yet a pattern.
MIN_OCCURRENCES = 2


# ──────────────────────────────────────────────────────────────────────────
# Public types
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class CorrectionPair:
    """One agent-was-wrong / oncall-said-this datum."""
    submitter: str | None
    incident_id: str
    agent_said: str | None
    oncall_said: str
    remediation: str | None
    ts_ms: int | None


@dataclass
class Cluster:
    """Group of corrections sharing service + alert-shape."""
    service: str
    alert_shape: str
    pairs: list[CorrectionPair] = field(default_factory=list)
    distinct_submitters: set[str] = field(default_factory=set)

    @property
    def occurrences(self) -> int:
        return len(self.pairs)

    @property
    def first_seen_ms(self) -> int | None:
        ts = [p.ts_ms for p in self.pairs if p.ts_ms]
        return min(ts) if ts else None

    @property
    def last_seen_ms(self) -> int | None:
        ts = [p.ts_ms for p in self.pairs if p.ts_ms]
        return max(ts) if ts else None


@dataclass
class DraftReport:
    generated_at_ms: int
    clusters: list[Cluster]
    skipped_below_threshold: int
    min_occurrences: int

    def to_markdown(self) -> str:
        return _render_markdown(self)


# ──────────────────────────────────────────────────────────────────────────
# Core
# ──────────────────────────────────────────────────────────────────────────


_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")
_BORING_WORDS = {
    "a", "an", "the", "and", "or", "but", "is", "are", "was",
    "in", "of", "on", "to", "for", "with", "after", "before",
    "from", "by", "at", "as", "this", "that", "it", "be",
    # Short-form units of measure -- they're shape noise.
    "ms", "s", "min", "h", "ago", "now",
}
# Used to strip leading severity / service prefix that some alerts carry.
_LEADING_NOISE = re.compile(r"^(sev[- ]?\d+\s*[:\-]?\s*)", re.IGNORECASE)


def alert_shape(description: str | None) -> str:
    """
    Reduce a free-form alert string to a stable shape token used for
    clustering. Drops numbers (so '5xx rate 12%' and '5xx rate 18%'
    collapse to the same cluster), normalises case, removes stop-words.

    The function is intentionally simple -- it's a hash, not nl-u.
    Anything fancier requires a model, and we want this to be cheap.
    """
    if not description:
        return "unknown"
    s = description.lower()
    s = _LEADING_NOISE.sub("", s)
    # Drop digits + dotted versions outright; they're noise for shape.
    s = re.sub(r"[\d.]+", " ", s)
    tokens = [
        t for t in _TOKEN_SPLIT.split(s)
        if t and t not in _BORING_WORDS and len(t) > 1
    ]
    if not tokens:
        return "unknown"
    # Keep only the first 4 meaningful tokens. More than that and the
    # clustering becomes too fine and you get singletons everywhere.
    return "-".join(tokens[:4])


def gather_corrections(records: Iterable[dict[str, Any]]) -> list[CorrectionPair]:
    """
    Pull (service, alert_shape, correction) tuples from raw feedback
    records. We need both the feedback record AND the incident it was
    attached to -- the feedback stores `incident_id` but not the alert
    body, so we rely on metadata the recorder bundles in.

    The store format is:
      {"incident_id": "...", "records": [ {feedback dict}, ... ],
       "alert": {service, description, ...}}

    The "alert" snapshot is written at append time so this works even
    after the in-memory INCIDENTS dict has rolled.
    """
    pairs: list[CorrectionPair] = []
    for rec in records:
        verdict = rec.get("verdict")
        if verdict not in {"thumbs_down", "incorrect"}:
            continue
        cause = rec.get("correct_root_cause")
        if not cause:
            continue
        pairs.append(CorrectionPair(
            submitter=rec.get("submitter"),
            incident_id=rec.get("incident_id", ""),
            agent_said=rec.get("agent_root_cause"),
            oncall_said=cause,
            remediation=rec.get("correct_remediation"),
            ts_ms=rec.get("ts_ms"),
        ))
    return pairs


def load_all_corrections() -> list[CorrectionPair]:
    """
    Walk the feedback store, attaching the alert snapshot saved on each
    incident-level blob so we can derive `service` + `alert_shape`.
    """
    pairs: list[CorrectionPair] = []
    blobs = FEEDBACK_STORE.list_recent(limit=100_000)
    for blob in blobs:
        incident_id = blob.get("incident_id", "")
        alert = blob.get("alert") or {}
        service = alert.get("service") or "unknown"
        shape = alert_shape(alert.get("description"))
        for rec in (blob.get("records") or []):
            if rec.get("verdict") not in {"thumbs_down", "incorrect"}:
                continue
            cause = rec.get("correct_root_cause")
            if not cause:
                continue
            pairs.append(CorrectionPair(
                submitter=rec.get("submitter"),
                incident_id=incident_id,
                agent_said=rec.get("agent_root_cause"),
                oncall_said=cause,
                remediation=rec.get("correct_remediation"),
                ts_ms=rec.get("ts_ms"),
            ))
            # carry shape/service on the pair as well via lambda close
            # (cheap: just patch attributes the renderer reads)
            pairs[-1].__dict__["service"] = service
            pairs[-1].__dict__["shape"] = shape
    return pairs


def draft(
    *,
    min_occurrences: int = MIN_OCCURRENCES,
) -> DraftReport:
    """
    Pull corrections, cluster them, and return a DraftReport.
    """
    pairs = load_all_corrections()
    clusters: dict[tuple[str, str], Cluster] = {}
    skipped = 0

    for p in pairs:
        service = p.__dict__.get("service", "unknown")
        shape = p.__dict__.get("shape", "unknown")
        key = (service, shape)
        if key not in clusters:
            clusters[key] = Cluster(service=service, alert_shape=shape)
        c = clusters[key]
        c.pairs.append(p)
        if p.submitter:
            c.distinct_submitters.add(p.submitter)

    # Filter: keep clusters with enough occurrences (and ≥1 distinct
    # submitter -- otherwise it's one person typing repeatedly).
    kept: list[Cluster] = []
    for c in clusters.values():
        if c.occurrences < min_occurrences:
            skipped += 1
            continue
        kept.append(c)

    # Sort by impact: more occurrences first, then more distinct submitters.
    kept.sort(key=lambda c: (-c.occurrences, -len(c.distinct_submitters)))

    return DraftReport(
        generated_at_ms=int(time.time() * 1000),
        clusters=kept,
        skipped_below_threshold=skipped,
        min_occurrences=min_occurrences,
    )


# ──────────────────────────────────────────────────────────────────────────
# Markdown rendering
# ──────────────────────────────────────────────────────────────────────────


def _render_markdown(report: DraftReport) -> str:
    lines = [
        "# Auto-drafted runbook entries",
        "",
        f"Generated at `{report.generated_at_ms}` (UTC ms).  ",
        "Each section below is **a draft** assembled from oncall corrections "
        "(`verdict ∈ thumbs_down|incorrect` with `correct_root_cause` set). "
        "Review before merging.",
        "",
        f"- **{len(report.clusters)}** cluster(s) ready for review",
        f"- **{report.skipped_below_threshold}** cluster(s) below the "
        f"`min_occurrences={report.min_occurrences}` threshold (suppressed)",
        "",
        "---",
        "",
    ]

    if not report.clusters:
        lines.append("_No clusters above threshold. Run again after more feedback._")
        return "\n".join(lines) + "\n"

    for c in report.clusters:
        lines.append(f"## `{c.service}` -- pattern: `{c.alert_shape}`")
        lines.append("")
        lines.append(
            f"- Occurrences: **{c.occurrences}**"
            f" -- distinct submitters: **{len(c.distinct_submitters)}**"
        )
        if c.first_seen_ms and c.last_seen_ms:
            lines.append(
                f"- Window: `{c.first_seen_ms}` → `{c.last_seen_ms}` (UTC ms)"
            )
        lines.append("")
        lines.append("### What the agent kept saying (and what oncall corrected)")
        lines.append("")
        for p in c.pairs[:10]:  # cap to avoid runaway noise
            agent_said = p.agent_said or "_(not recorded)_"
            lines.append(f"- **agent:** {agent_said}")
            lines.append(f"  **oncall:** {p.oncall_said}")
            if p.remediation:
                lines.append(f"  **action:** {p.remediation}")
            lines.append("")
        if len(c.pairs) > 10:
            lines.append(f"_…and {len(c.pairs) - 10} more occurrences_")
            lines.append("")

        lines.append("### Suggested runbook entry")
        lines.append("")
        rem = _pick_modal(p.remediation for p in c.pairs)
        cause = _pick_modal(p.oncall_said for p in c.pairs)
        lines.append(f"> When `{c.service}` fires `{c.alert_shape}`-shaped "
                     f"alerts, the most common true root cause is: **{cause}**.")
        if rem:
            lines.append(">")
            lines.append(f"> Recommended first action: `{rem}`")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines) + "\n"


def _pick_modal(values: Iterable[str | None]) -> str | None:
    """
    Most common non-empty value in `values`. Cheap mode picker -- when
    there's a tie, returns whichever pops out of the dict first.
    """
    counts: dict[str, int] = {}
    for v in values:
        if v:
            counts[v] = counts.get(v, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda x: x[1])[0]
