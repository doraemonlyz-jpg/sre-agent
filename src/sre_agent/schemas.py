"""
Strongly-typed I/O contracts for every agent in the system.

These Pydantic schemas are the **production version** of the EVIDENCE-block
text contract from v0. They give us three superpowers:

1. **Structured-output enforcement** — LangChain's `with_structured_output()`
   makes the LLM return JSON that fits a schema. No more text-parsing.
2. **Hallucination-resistant** — fields like `hits: int` and `confidence: float`
   cannot be fabricated as prose. They're typed.
3. **Auto-rejection on missing fields** — Pydantic raises if a worker forgets
   a required field. This is our structural gate.

Every node in `graph.py` either consumes or produces one of these.
"""

from __future__ import annotations

import operator
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────────────────────────────────
# Alert input
# ──────────────────────────────────────────────────────────────────────────


class Severity(str, Enum):
    SEV_1 = "SEV-1"  # full outage
    SEV_2 = "SEV-2"  # major degradation
    SEV_3 = "SEV-3"  # minor / latency
    SEV_4 = "SEV-4"  # informational


class AlertIn(BaseModel):
    """The webhook payload from PagerDuty / Datadog. Minimal fields."""

    service: str = Field(..., description="The affected service name, e.g. 'checkout-api'.")
    severity: Severity
    description: str = Field(..., description="One-line human-readable alert text.")
    started_at: datetime = Field(..., description="When the alert first fired (UTC).")
    tags: list[str] = Field(default_factory=list)
    scenario_id: str | None = Field(
        default=None,
        description="When using the MockProvider, which scenario to pin to.",
    )

    model_config = {"frozen": True}


# ──────────────────────────────────────────────────────────────────────────
# Evidence — what each worker reports back
# ──────────────────────────────────────────────────────────────────────────


class EvidenceResult(str, Enum):
    """Mirror of the v0 `<RESULT>` tag — only thing the PM branches on."""

    FOUND = "FOUND"  # real signal found
    NO_SIGNAL = "NO_SIGNAL"  # queried successfully, nothing anomalous
    ERROR = "ERROR"  # tool / API failure — caller decides


class _EvidenceBase(BaseModel):
    """Common shape for any worker's evidence reply."""

    source: str
    result: EvidenceResult
    interpretation: str = Field(
        ...,
        description="One short sentence — what this evidence means, in plain English.",
        max_length=400,
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Verifiable IDs the PM can re-query (log IDs, trace IDs, PR URLs).",
    )


class LogsEvidence(_EvidenceBase):
    source: Literal["datadog-logs"] = "datadog-logs"
    hits: int = Field(..., ge=0)
    first_at: datetime | None = None
    peak_at: datetime | None = None
    top_messages: list[dict[str, Any]] = Field(default_factory=list)


class MetricSnapshot(BaseModel):
    name: str
    baseline: float
    peak: float
    peak_at: datetime | None = None
    verdict: str  # "NORMAL" | "SPIKE (192x)" | ...

    @property
    def is_spike(self) -> bool:
        return "SPIKE" in self.verdict


class MetricsEvidence(_EvidenceBase):
    source: Literal["datadog-metrics"] = "datadog-metrics"
    metrics: list[MetricSnapshot] = Field(default_factory=list)
    correlation: str | None = Field(
        default=None,
        description="If 2+ metrics spike at the same minute, name them.",
    )


class HotSpan(BaseModel):
    service: str
    name: str
    baseline_ms: float
    median_ms: float
    ratio: str  # e.g. "2810x"


class TracesEvidence(_EvidenceBase):
    source: Literal["datadog-apm"] = "datadog-apm"
    traces_inspected: int = Field(..., ge=0)
    error_rate: str = Field(..., description="e.g. '14/18'")
    hot_span: HotSpan | None = None
    downstream_suspect: str | None = None


class DeployRecord(BaseModel):
    service: str
    sha: str
    pr_url: str
    pr_title: str
    author: str
    deployed_at: datetime
    minutes_before: float = Field(..., ge=0)
    suspect: Literal["HIGH", "MEDIUM", "LOW"]


class DeploysEvidence(_EvidenceBase):
    source: Literal["deploys"] = "deploys"
    deploys: list[DeployRecord] = Field(default_factory=list)
    config_changes: list[str] = Field(default_factory=list)


AnyEvidence = LogsEvidence | MetricsEvidence | TracesEvidence | DeploysEvidence


# ──────────────────────────────────────────────────────────────────────────
# Hypothesis & remediation
# ──────────────────────────────────────────────────────────────────────────


class Hypothesis(BaseModel):
    """A ranked root-cause hypothesis with citations to evidence."""

    title: str = Field(..., max_length=120)
    detail: str = Field(..., max_length=1200)
    confidence: float = Field(..., ge=0.0, le=1.0)
    supporting_evidence: list[Literal["logs", "metrics", "traces", "deploys"]] = Field(
        default_factory=list,
        description="Which evidence sources back this hypothesis.",
    )
    contradicting_evidence: list[Literal["logs", "metrics", "traces", "deploys"]] = Field(
        default_factory=list,
    )
    why_not_alternative: str = Field(default="", max_length=400)

    @field_validator("supporting_evidence", "contradicting_evidence")
    @classmethod
    def _no_dup(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))  # dedupe, preserve order


class HypothesisList(BaseModel):
    """The full hypothesis payload from Hypothesis Generator."""

    hypotheses: list[Hypothesis] = Field(..., min_length=1, max_length=5)
    notes: str = Field(default="", max_length=600)

    @property
    def top(self) -> Hypothesis:
        return max(self.hypotheses, key=lambda h: h.confidence)


class RemediationRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    NONE = "NONE"  # informational / "do NOT do X" anti-pattern


class RemediationAction(BaseModel):
    """A single suggested remediation step. Human runs it; agent never does."""

    title: str = Field(..., max_length=120)
    command: str = Field(
        ...,
        description="The exact shell command, copy-pasteable.",
        max_length=600,
    )
    why: str = Field(..., max_length=400)
    expected_effect: str = Field(..., max_length=400)
    reversal: str = Field(
        ...,
        description="How to undo this action if it makes things worse.",
        max_length=600,
    )
    risk: RemediationRisk


class RemediationPlan(BaseModel):
    """Output of the Remediation Suggester."""

    actions: list[RemediationAction] = Field(default_factory=list, max_length=5)
    do_not_do: list[str] = Field(
        default_factory=list,
        description="Anti-patterns: things an over-eager oncall might try and shouldn't.",
        max_length=5,
    )


# ──────────────────────────────────────────────────────────────────────────
# Incident report (final artifact)
# ──────────────────────────────────────────────────────────────────────────


class IncidentReport(BaseModel):
    """The full state of an incident — written to disk and shown in the UI."""

    incident_id: str
    alert: AlertIn
    phase: Literal["investigating", "diagnosed", "no_signal", "failed"]
    started_at: datetime
    diagnosed_at: datetime | None = None
    diagnosis_ms: int | None = None

    logs: LogsEvidence | None = None
    metrics: MetricsEvidence | None = None
    traces: TracesEvidence | None = None
    deploys: DeploysEvidence | None = None

    hypotheses: HypothesisList | None = None
    remediation: RemediationPlan | None = None

    source: Literal["incident-pm", "watchdog"] = "incident-pm"
    reason: str = ""


# ──────────────────────────────────────────────────────────────────────────
# LangGraph state — the dict passed between nodes
# ──────────────────────────────────────────────────────────────────────────


class GraphState(TypedDict, total=False):
    """
    The graph's shared mutable state. Total=False so each node can read+write
    only the keys it cares about (LangGraph merges partial returns).
    """

    # Inputs
    alert: AlertIn

    # Per-source evidence (filled by parallel workers)
    logs: LogsEvidence | None
    metrics: MetricsEvidence | None
    traces: TracesEvidence | None
    deploys: DeploysEvidence | None

    # Synthesized
    hypotheses: HypothesisList | None
    remediation: RemediationPlan | None

    # Final
    report: IncidentReport | None

    # Trace log for the UI's live activity feed.
    # `operator.add` reducer means parallel nodes' events are concatenated.
    events: Annotated[list[dict[str, Any]], operator.add]
