"""
Synthetic-data seeder -- the engine that lets us develop and demo L6
features without a live production deployment.

Why this exists
---------------
L5 built the pipes for the flywheel:
  * Per-incident harness records tagged with `prompt_sha` per agent.
  * Feedback store with verdict + correction + per-record SHAs.
  * Response cache with TTL.

But the pipes are empty when there's no production traffic. The L6
features (winner promotion, auto-runbook draft, confidence calibration)
are all consumers of this data -- they're moot until there's data.

This module fabricates plausible incidents + feedback + LLM call
records drawn from production-shaped distributions. After seeding:
  * `/api/feedback/summary` shows a real CSAT curve.
  * `/api/harness/calls` grouped by `prompt_sha` shows the variant's
    measurable difference from baseline.
  * `/api/incidents` lists a believable backlog.
  * L6.1 cron jobs have data to act on.

What's "plausible"
------------------
We bias the data so the L6 mechanisms have something to detect:

  * 90% of hypothesis-gen calls used the baseline prompt; 10% used the
    `conservative` variant.
  * Conservative variant has a 5-8 percentage-point higher thumbs-up
    rate (small enough to be realistic, big enough that with N=1000
    a chi-square test rejects null).
  * SEV-1 incidents have lower thumbs-up rate (they're hard).
  * About 25% of incidents get no oncall review (real life).
  * Repeated alerts within 5 minutes produce cache hits (~10% of total).

Where the data lives
--------------------
  * Feedback: `SRE_FEEDBACK_DIR/*.json` (real on-disk records via FeedbackStore).
  * Harness records: in-process `RECORDER` ring buffer (max=10_000 default,
    so a 1000-incident seed with ~6 records each just fits).
  * INCIDENTS dict: in-process. Pokes the dashboard's dict directly when
    `seed_into_dashboard()` is called from the same process (use the
    `SRE_SEED_ON_BOOT=N` env var, or `sre-agent seed --n N --on-boot`).

Determinism
-----------
`seed(n=N, seed=42)` is reproducible -- same RNG seed → identical output.
This matters for tests that assert "after seeding, winner cron picks
conservative" -- flaky tests poison CI.
"""

from __future__ import annotations

import logging
import random
import time
import uuid
from dataclasses import dataclass
from typing import Any

from sre_agent.feedback import STORE as FEEDBACK_STORE
from sre_agent.feedback import make_record as make_feedback_record
from sre_agent.harness import RECORDER, LLMCallRecord

log = logging.getLogger("sre_agent.seed")


# ──────────────────────────────────────────────────────────────────────────
# Realistic distributions
# ──────────────────────────────────────────────────────────────────────────

# A mix of realistic service names: web app, payments, search, infra.
# Production diversity matters because A/B + winner detection have to
# work across services with very different alert shapes.
_SERVICES = [
    "checkout-api", "payments-gateway", "auth-service",
    "user-profile", "cart-service", "order-pipeline",
    "search-suggest", "recommend-feed", "video-encoder",
    "live-stream-edge", "comment-svc", "notification-fanout",
    "inventory-sync", "promo-engine", "price-cache",
    "image-thumbnail", "cdn-router", "ad-bidder",
    "session-store", "rate-limiter-edge",
]

# weights add to 1.0 -- SEV-3 is the bread-and-butter, SEV-1 is rare.
_SEVERITY_WEIGHTS = [
    ("SEV-1", 0.05),
    ("SEV-2", 0.25),
    ("SEV-3", 0.50),
    ("SEV-4", 0.20),
]

# (template, hypothesis title, evidence likelihood)
# Each template represents a recurring real-world failure mode. Used so
# the resulting alerts read like genuine pages rather than nonsense.
_FAILURE_PATTERNS = [
    {
        "desc": "p99 latency {p99}ms spiking on /checkout, error rate {err}%",
        "hypothesis": "Redis connection pool exhaustion under load",
        "remediation": "scale checkout-api pool size from 50→200",
        "p99_range": (1500, 4000), "err_range": (3, 15),
        "true_positive": True,
    },
    {
        "desc": "5xx rate {err}% sustained for {dur}s after deploy of {pr}",
        "hypothesis": "Recent deploy introduced a null-pointer in checkout flow",
        "remediation": "rollback deploy {pr}",
        "err_range": (8, 25), "dur_range": (60, 600), "pr_range": (10000, 99999),
        "true_positive": True,
    },
    {
        "desc": "downstream service {svc} returning 502 -- error budget burning at {burn}x",
        "hypothesis": "{svc} health-check failure cascade",
        "remediation": "page {svc} oncall; circuit-break in client",
        "burn_range": (3, 20),
        "true_positive": True,
    },
    {
        "desc": "memory usage {mem}% on {svc} -- OOM kill predicted in {eta}m",
        "hypothesis": "Leak in v{ver} of the request-context middleware",
        "remediation": "rolling restart of {svc}",
        "mem_range": (85, 99), "eta_range": (3, 30), "ver_range": (10, 99),
        "true_positive": True,
    },
    {
        "desc": "noisy probe alert: p99 {p99}ms briefly, recovered in {dur}s",
        "hypothesis": "(no actionable signal -- likely a transient probe blip)",
        "remediation": "(no action)",
        "p99_range": (200, 800), "dur_range": (5, 30),
        "true_positive": False,
    },
    {
        "desc": "synthetic-monitor flap: 3 consecutive failed checks on {svc}",
        "hypothesis": "(monitor saw a deploy + restart, normal recovery)",
        "remediation": "(no action)",
        "true_positive": False,
    },
]


# Per-agent LLM call profile: (mean latency ms, latency stdev, mean input
# tokens, mean output tokens). These match the rough shape we observed
# running gpt-oss:20b locally -- close enough that the "harness" panel on
# the dashboard looks realistic.
_AGENT_PROFILES: dict[str, dict[str, float]] = {
    "log-detective":     {"lat_mean": 3200, "lat_std": 900,  "in_tok": 800,  "out_tok": 300},
    "metrics-analyst":   {"lat_mean": 4100, "lat_std": 1100, "in_tok": 600,  "out_tok": 250},
    "trace-reader":      {"lat_mean": 5200, "lat_std": 1500, "in_tok": 700,  "out_tok": 280},
    "deploy-historian":  {"lat_mean": 2300, "lat_std": 700,  "in_tok": 400,  "out_tok": 180},
    "hypothesis-gen":    {"lat_mean": 6400, "lat_std": 1800, "in_tok": 2000, "out_tok": 500},
    "remediation-sug":   {"lat_mean": 5100, "lat_std": 1500, "in_tok": 1500, "out_tok": 400},
}


# Fake prompt SHAs. In a real environment these are computed from
# persona content via personas.load_with_sha(); here we hard-code so the
# L6 winner cron has unambiguous groups to compare without depending on
# the actual persona file bytes.
#
# The variants are calibrated so the winner cron's matrix output tells
# DIFFERENT stories per agent -- promote, hold-thin-delta,
# hold-baseline-already-best, no-variant -- demonstrating the system's
# range of decisions, not just "everything promotes":
_PROMPT_SHAS = {
    "log-detective":    {"baseline": "09c3b1aa", "strict_citations":  "31d7af44"},
    "metrics-analyst":  {"baseline": "7f2d4e10", "anomaly_focused":   "6ec88011"},
    "trace-reader":     {"baseline": "bb14c2c9"},
    "deploy-historian": {"baseline": "c4d3c986"},
    "hypothesis-gen":   {"baseline": "0c8f14d5", "conservative":      "9a4e2b73"},
    "remediation-sug":  {"baseline": "812a99ee", "low_risk_first":    "ad2b6e09"},
}


# Per-SHA additive contributions to the true-positive thumbs-up rate.
#
# Model: the verdict is the SUM of each agent's contribution. A
# baseline SHA contributes 0; a variant contributes its calibrated
# delta. This is additive on purpose — when oncall judges a report,
# they're judging the JOINT output of all agents, so any agent's
# variant should move the dial proportionally.
#
# Calibrated so the winner cron's per-agent matrix tells a complete
# story (each agent lands on a different decision):
#
#   hypothesis-gen.conservative   (+16pp)  -> PROMOTE (strong)
#   metrics-analyst.anomaly       (+8pp)   -> PROMOTE at N>=2000
#   log-detective.strict          (+2pp)   -> HOLD (under min_delta_pp)
#   remediation-sug.low_risk      (-7pp)   -> HOLD (baseline wins clearly)
#
# Realistic shape: A/B experiments rarely yield clear winners. A
# matrix saying "we tried 4 variants, 2 panned out, 2 didn't" is the
# right advertisement for a working flywheel; one where everything
# wins by 20pp looks fake.
_SHA_DELTA_PP = {
    "0c8f14d5":  0,    # hypothesis-gen baseline
    "9a4e2b73": 16,    # hypothesis-gen conservative

    "7f2d4e10":  0,    # metrics-analyst baseline
    "6ec88011":  8,    # metrics-analyst anomaly-focused

    "09c3b1aa":  0,    # log-detective baseline
    "31d7af44":  2,    # log-detective strict-citations

    "812a99ee":  0,    # remediation-sug baseline
    "ad2b6e09": -7,    # remediation-sug low-risk-first (variant LOSES by 7pp)

    "bb14c2c9":  0,    # trace-reader (no variant — always 0)
    "c4d3c986":  0,    # deploy-historian (no variant — always 0)
}

# Base thumbs-up rate for TP incidents (with everyone on baseline).
_BASE_TP_RATE = 0.62


# ──────────────────────────────────────────────────────────────────────────
# Public seeding API
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class SeedResult:
    n_incidents: int
    n_feedback: int
    n_llm_records: int
    n_cache_hits: int
    duration_s: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_incidents": self.n_incidents,
            "n_feedback": self.n_feedback,
            "n_llm_records": self.n_llm_records,
            "n_cache_hits": self.n_cache_hits,
            "duration_s": round(self.duration_s, 2),
        }


def seed(
    *,
    n: int = 1000,
    seed_value: int = 42,
    days_back: int = 7,
    ab_fraction: float = 0.1,
    reset_first: bool = True,
    incidents_dict: dict[str, dict[str, Any]] | None = None,
) -> SeedResult:
    """
    Generate `n` synthetic incidents with feedback + harness records.

    `incidents_dict` is the dashboard's INCIDENTS map. When the dashboard
    is in the same process, pass `dashboard.app.INCIDENTS` so the UI
    shows the seeded incidents immediately. When this is called from a
    standalone CLI (no dashboard), pass None -- the feedback + harness
    records still land and are visible whenever the dashboard reads
    them.

    `reset_first=True` clears the feedback store + harness buffer before
    seeding. Without this, repeated `sre-agent seed` calls would
    double-count.
    """
    rng = random.Random(seed_value)
    started = time.time()

    if reset_first:
        FEEDBACK_STORE.reset()
        # The recorder doesn't expose `clear` -- it's a deque(maxlen=N)
        # so old records get evicted naturally. Still, force a clean
        # slate to keep summary math predictable.
        try:
            RECORDER._records.clear()           # type: ignore[attr-defined]
            RECORDER._by_incident.clear()       # type: ignore[attr-defined]
        except AttributeError:
            pass
        if incidents_dict is not None:
            incidents_dict.clear()

    n_feedback = 0
    n_llm = 0
    n_cache_hits = 0

    # Spread incidents over the last `days_back` days, biased toward
    # business hours (8a-10p) and toward more-recent days.
    now = time.time()
    window_s = days_back * 86400
    business_bias_weights = _build_business_bias()

    # Build a re-fire pool. After every Kth incident we pick an alert
    # the agent has already seen and "re-fire" it → cache hit.
    recent_alerts: list[tuple[str, str, str]] = []

    for i in range(n):
        # Pick a service-weighted incident
        ts = now - rng.random() * window_s
        # Apply business-hour bias by skewing the random offset
        ts = _apply_business_bias(ts, rng, business_bias_weights)
        ts_ms = int(ts * 1000)

        service = rng.choice(_SERVICES)
        severity = _weighted_choice(rng, _SEVERITY_WEIGHTS)
        pattern = rng.choice(_FAILURE_PATTERNS)

        # Roll a cache hit ~10% of the time, starting from incident 50 so
        # the recent_alerts pool is non-empty.
        is_cache_hit = (
            i > 50
            and recent_alerts
            and rng.random() < 0.10
        )

        if is_cache_hit:
            service, severity, desc = rng.choice(recent_alerts)
        else:
            desc = _fill_template(pattern["desc"], pattern, rng)
            recent_alerts.append((service, severity, desc))
            if len(recent_alerts) > 100:
                recent_alerts.pop(0)

        incident_id = uuid.uuid4().hex[:10]
        true_positive = pattern["true_positive"]

        # ── decide which prompt SHA this incident used (A/B routing) ──
        # Each agent that HAS a non-baseline variant gets its own
        # independent A/B coin flip. This matches reality: prompt
        # experiments are usually launched at different cadences per
        # agent. Independent flips also give the winner cron more
        # realistic correlation structure -- a single incident might
        # land on baseline for one agent and variant for another.
        prompt_shas = {agent: shas["baseline"] for agent, shas in _PROMPT_SHAS.items()}
        on_variant = False  # tracked specifically for hypothesis-gen (it drives the confidence calibration below)
        if not is_cache_hit:
            for agent, shas in _PROMPT_SHAS.items():
                variant_keys = [k for k in shas if k != "baseline"]
                if not variant_keys:
                    continue
                if rng.random() < ab_fraction:
                    chosen = rng.choice(variant_keys)
                    prompt_shas[agent] = shas[chosen]
                    if agent == "hypothesis-gen":
                        on_variant = True

        # ── harness records (skip when cache hit -- cache short-circuits LLM) ──
        if is_cache_hit:
            RECORDER.record(LLMCallRecord(
                id=uuid.uuid4().hex[:12],
                kind="cache_hit",
                ts=ts,
                agent="harness",
                incident_id=incident_id,
                detail={"reused_from": rng.choice(recent_alerts)[2][:40]},
            ))
            n_cache_hits += 1
        else:
            for agent, sha in prompt_shas.items():
                rec = _build_llm_record(agent, sha, incident_id, ts, rng)
                RECORDER.record(rec)
                n_llm += 1

        # ── phase + report ──
        phase, hypothesis, remediation = _decide_phase(
            true_positive=true_positive,
            severity=severity,
            on_variant=on_variant,
            pattern=pattern,
            rng=rng,
        )

        # ── INCIDENTS dict (when dashboard is in-process) ──
        if incidents_dict is not None:
            incidents_dict[incident_id] = {
                "id": incident_id,
                "scenario_id": None,
                "alert": {
                    "service": service,
                    "severity": severity,
                    "description": desc,
                    "started_at": _iso(ts),
                    "tags": [],
                },
                "phase": phase,
                "started_at": ts_ms,
                "diagnosed_at": ts_ms + rng.randint(3000, 20_000),
                "diagnosis_ms": rng.randint(3000, 20_000),
                "events": [],
                "findings": {},
                "hypothesis": hypothesis,
                "remediation": remediation,
                "report_json": None,
                "model_tier": rng.choices(
                    ["rule", "cheap", "premium"], weights=[0.20, 0.65, 0.15]
                )[0],
                "served_from_cache": is_cache_hit,
                "cache_origin_incident_id": None,
                "_synthetic": True,
            }

        # ── feedback (75% review rate) ──
        if rng.random() < 0.75:
            verdict = _draw_verdict(
                phase=phase,
                true_positive=true_positive,
                severity=severity,
                prompt_shas=prompt_shas,
                rng=rng,
                agent_confidence=(hypothesis or {}).get("confidence"),
            )
            fb = make_feedback_record(
                verdict=verdict,
                submitter=f"oncall-{rng.choice(['alice','bob','carol','dave','eve'])}",
                rating=rng.choice([None, None, 3, 4, 4, 5]),
                correct_root_cause=(
                    _fake_root_cause(service, pattern, rng)
                    if verdict in ("thumbs_down", "incorrect")
                    else None
                ),
                correct_remediation=(
                    _fake_remediation(service, rng)
                    if verdict == "thumbs_down"
                    else None
                ),
                free_text=None,
                agent_root_cause=(hypothesis or {}).get("top") if hypothesis else None,
                # Only attach `agent_confidence` for actual diagnostic
                # predictions. The `no_signal` phase records a deliberate
                # abstention ("we didn't find a signal") -- its
                # nominally-low confidence number is about the NULL
                # hypothesis, not about a real prediction, and feeding
                # it to the calibrator just adds bimodal noise that PAV
                # has to pool away. Same for timeouts.
                agent_confidence=(
                    (hypothesis or {}).get("confidence")
                    if (hypothesis and phase == "diagnosed")
                    else None
                ),
                prompt_shas_seen=prompt_shas,
                tags=(
                    ["false-positive"]
                    if not true_positive and verdict in ("incorrect", "thumbs_down")
                    else []
                ),
            )
            FEEDBACK_STORE.append(
                incident_id,
                fb,
                alert={
                    "service": service,
                    "severity": severity,
                    "description": desc,
                    "started_at": _iso(ts),
                },
            )
            n_feedback += 1

    return SeedResult(
        n_incidents=n,
        n_feedback=n_feedback,
        n_llm_records=n_llm,
        n_cache_hits=n_cache_hits,
        duration_s=time.time() - started,
    )


# ──────────────────────────────────────────────────────────────────────────
# Internals
# ──────────────────────────────────────────────────────────────────────────


def _weighted_choice(rng: random.Random, weighted: list[tuple[str, float]]) -> str:
    items, weights = zip(*weighted, strict=True)
    return rng.choices(items, weights=weights, k=1)[0]


def _build_business_bias() -> list[float]:
    """Per-hour-of-day weights, peak 8a-10p, trough 2a-6a."""
    w = [0.3, 0.2, 0.15, 0.15, 0.15, 0.2,
         0.4, 0.6, 1.0, 1.2, 1.3, 1.3,
         1.4, 1.4, 1.3, 1.2, 1.2, 1.3,
         1.2, 1.1, 1.0, 0.8, 0.6, 0.4]
    return w


def _apply_business_bias(ts: float, rng: random.Random, weights: list[float]) -> float:
    """Skew the chosen timestamp toward business hours so the demo's
    /api/incidents list doesn't look uniformly random."""
    hour = int((ts % 86400) // 3600)
    if rng.random() > weights[hour] / max(weights):
        delta = rng.choice([-1, 1]) * rng.randint(3600, 6 * 3600)
        return ts + delta
    return ts


def _fill_template(tpl: str, pattern: dict, rng: random.Random) -> str:
    out = tpl
    if "{p99}" in tpl:
        out = out.replace("{p99}", str(rng.randint(*pattern["p99_range"])))
    if "{err}" in tpl:
        out = out.replace("{err}", str(rng.randint(*pattern["err_range"])))
    if "{dur}" in tpl:
        out = out.replace("{dur}", str(rng.randint(*pattern["dur_range"])))
    if "{pr}" in tpl:
        out = out.replace("{pr}", "#" + str(rng.randint(*pattern["pr_range"])))
    if "{svc}" in tpl:
        out = out.replace("{svc}", rng.choice(_SERVICES))
    if "{burn}" in tpl:
        out = out.replace("{burn}", str(rng.randint(*pattern["burn_range"])))
    if "{mem}" in tpl:
        out = out.replace("{mem}", str(rng.randint(*pattern["mem_range"])))
    if "{eta}" in tpl:
        out = out.replace("{eta}", str(rng.randint(*pattern["eta_range"])))
    if "{ver}" in tpl:
        out = out.replace("{ver}", str(rng.randint(*pattern["ver_range"])))
    return out


def _build_llm_record(
    agent: str, sha: str, incident_id: str, ts: float, rng: random.Random
) -> LLMCallRecord:
    profile = _AGENT_PROFILES[agent]
    latency = max(
        300.0,
        rng.gauss(profile["lat_mean"], profile["lat_std"]),
    )
    # 1-2% error rate on LLM calls so the harness panel shows non-zero "errors"
    is_err = rng.random() < 0.015
    return LLMCallRecord(
        id=uuid.uuid4().hex[:12],
        kind="llm_call",
        ts=ts,
        agent=agent,
        incident_id=incident_id,
        model="gpt-oss:20b" if agent in {"hypothesis-gen", "remediation-sug"} else "qwen2.5-coder:7b",
        role="orchestrator" if agent in {"hypothesis-gen", "remediation-sug"} else "worker",
        prompt_sha=sha,
        latency_ms=latency,
        input_tokens=int(profile["in_tok"] + rng.gauss(0, profile["in_tok"] * 0.2)),
        output_tokens=int(profile["out_tok"] + rng.gauss(0, profile["out_tok"] * 0.2)),
        status="error" if is_err else "ok",
        error="timeout after 30s" if is_err else None,
    )


def _decide_phase(
    *,
    true_positive: bool,
    severity: str,
    on_variant: bool,
    pattern: dict,
    rng: random.Random,
) -> tuple[str, dict | None, list | None]:
    # 8% of incidents time-out before diagnosis (sev independent)
    if rng.random() < 0.03:
        return "timeout", None, None

    if not true_positive:
        # Most of these correctly land in no_signal -- that's a WIN, not a miss
        return "no_signal", {
            "top": "no actionable signal found",
            "detail": "evidence blocks were thin or contradictory",
            "confidence": round(rng.uniform(0.10, 0.30), 2),
            "supporting_evidence": [],
        }, []

    # True positives: synthesise a deliberately MISCALIBRATED confidence.
    #
    # Empirically, raw LLM confidence on diagnostic tasks tends to be
    # over-confident in the upper range: the model says "90% sure" and
    # is right only ~65% of the time. We mimic that here so the L6.3
    # calibrator (`sre_agent.calibration.IsotonicCalibrator`) has a
    # non-trivial mapping to learn -- otherwise its training set looks
    # already-calibrated and we can't demonstrate it actually working.
    #
    # Concretely:
    #   - Baseline draws confidence in [0.65, 0.95] (over-confident).
    #   - Conservative variant draws in [0.55, 0.85] (closer to honest).
    # SEV-1 incidents get an extra over-confidence bump because the
    # model has less time to reason in the prompt template.
    base_conf = rng.uniform(0.65, 0.95)
    if on_variant:
        # Conservative variant is more rigorous about citing -- emits
        # lower numbers on average.
        base_conf = rng.uniform(0.55, 0.85)
    if severity == "SEV-1":
        base_conf = min(0.98, base_conf + rng.uniform(0.0, 0.05))

    hyp = {
        "top": pattern["hypothesis"],
        "detail": pattern["hypothesis"] + " -- cited evidence: logs + metrics + deploys",
        "confidence": round(base_conf, 2),
        "supporting_evidence": rng.sample(
            ["logs", "metrics", "traces", "deploys", "runbooks"],
            k=rng.randint(2, 4),
        ),
    }
    rem = [
        {
            "title": pattern["remediation"][:60],
            "command": "kubectl rollout undo deploy/" + pattern["remediation"].split()[-1][:30],
            "risk": rng.choice(["LOW", "MEDIUM", "HIGH"]),
            "why": "based on " + ", ".join(hyp["supporting_evidence"]),
        }
    ]
    return "diagnosed", hyp, rem


def _draw_verdict(
    *,
    phase: str,
    true_positive: bool,
    severity: str,
    prompt_shas: dict[str, str],
    rng: random.Random,
    agent_confidence: float | None = None,
) -> str:
    """
    Per-incident verdict, biased so the data carries the signals L6
    features should detect:

      * Each agent's variant adds its own delta to the base TP rate.
      * Higher `agent_confidence` -> modestly higher p_up. This is the
        signal the L6.3 calibrator learns: the agent's confidence
        number carries SOME information about accuracy, but is
        over-stated (saying "90%" when really 70%).
      * SEV-1 is harder -> lower thumbs-up.
      * False positives flagged correctly by `no_signal` get thumbs-up
        despite "no diagnosis" (oncall appreciates restraint).
      * Timeouts overwhelmingly thumbs-down.

    The additive model means an incident on (hypothesis-gen.variant +
    metrics-analyst.variant) has a higher p_up than one on either
    alone. The winner cron's per-agent groups average over the OTHER
    agents' splits, so each agent's variant signal still surfaces
    cleanly in its own group's win rate -- exactly the way real prod
    A/B data behaves.
    """
    if phase == "timeout":
        return rng.choices(["thumbs_down", "incorrect"], weights=[0.7, 0.3])[0]

    # Sum each agent's contribution -- baseline shas contribute 0,
    # variant shas contribute their calibrated delta in percentage points.
    total_delta_pp = sum(_SHA_DELTA_PP.get(sha, 0) for sha in prompt_shas.values())
    p_up = _BASE_TP_RATE + (total_delta_pp / 100.0)

    # SEV-1 penalty: hard incidents
    if severity == "SEV-1":
        p_up -= 0.10

    # Confidence -> outcome bias (L6.3 calibration signal).
    #
    # We linearly shift p_up based on how confident the agent was, with
    # a deliberately shallow slope so the model stays OVER-confident:
    #
    #   raw=0.65 -> p_up shift =  0.00 (baseline)
    #   raw=0.95 -> p_up shift = +0.18 (high conf -> moderately better)
    #
    # End-state: an agent saying "95%" is actually right ~80% of the
    # time (overconfidence gap of ~15pp at the top), saying "65%" is
    # right ~55% (gap of ~10pp at the bottom). PAV isotonic regression
    # learns to map raw 0.95 -> ~0.80, raw 0.65 -> ~0.55, etc.
    if agent_confidence is not None and phase == "diagnosed":
        # Center the shift around 0.65 (the bottom of the TP confidence range).
        p_up += (agent_confidence - 0.65) * 0.60

    # No-signal on true negative -> oncall happy (correct restraint).
    # The variant's evidence-quality delta doesn't apply here -- the
    # report's contents are the same "no signal" either way.
    if not true_positive and phase == "no_signal":
        p_up = max(_BASE_TP_RATE + 0.18, 0.80)
    # No-signal on TRUE positive -> agent missed it; bad regardless of variant.
    if true_positive and phase == "no_signal":
        p_up = 0.20

    p_up = max(0.05, min(0.95, p_up))
    if rng.random() < p_up:
        # 80% thumbs_up, 20% "correct" (oncall affirmed the root cause)
        return rng.choices(["thumbs_up", "correct"], weights=[0.80, 0.20])[0]
    # 70% thumbs_down, 30% "incorrect" (formal flag)
    return rng.choices(["thumbs_down", "incorrect"], weights=[0.70, 0.30])[0]


def _fake_root_cause(service: str, pattern: dict, rng: random.Random) -> str:
    samples = [
        f"actually a downstream {rng.choice(_SERVICES)} timeout, not {service}",
        f"queue head-of-line blocking in {service}, not what the agent said",
        f"DNS resolution lag in the {service} sidecar",
        f"shared-tenant noisy-neighbor: kafka topic for {rng.choice(_SERVICES)} was filling our partition",
        "feature flag flipped to 100% an hour earlier; not a deploy regression",
    ]
    return rng.choice(samples)


def _fake_remediation(service: str, rng: random.Random) -> str:
    samples = [
        f"disable feature flag svc.{service}.new_path",
        f"increase {service} concurrency limit to 2x and re-rate-limit upstream",
        "restart the sidecar, not the main container",
        f"page the {rng.choice(_SERVICES)} oncall; the real ownership is downstream",
        "no-op; this is a known flaky synthetic monitor",
    ]
    return rng.choice(samples)


def _iso(ts: float) -> str:
    import datetime as _dt
    return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).isoformat()
