"""
L6.1 -- A/B winner promotion.

The goal: turn the feedback flywheel into an automatic prompt-improvement
loop. We're paid by results, not vibes, so the decision MUST be:

  1.  Honest about uncertainty. With a few hundred ratings, the noise
      floor is real. Don't promote a variant just because it looks
      better by a percentage point.
  2.  Conservative by default. Hold > promote-on-thin-evidence.
      Misfires erode trust in the system fast.
  3.  Self-documenting. The output is a decision record -- what we saw,
      what test we ran, what alpha we used, and what to do next -- written
      as Markdown so it slots straight into a PR description.

Inputs
------
The feedback store (disk-persistent JSON, one file per incident). Each
record carries `prompt_shas_seen: dict[agent → sha]`, written at the
moment the report was generated. This is the durable join key -- even if
the ephemeral harness ring buffer has rolled, the feedback record still
remembers which prompt produced each judged outcome.

What "winner" means here
------------------------
For one agent at a time, partition feedback records by the prompt_sha
that produced them. Each group has (n, positives). The positive event
is `verdict ∈ {thumbs_up, correct}`. We then:

  * Compute the Wilson score interval for each group's true rate.
  * Pick the highest-mean group as the candidate.
  * Run a two-proportion z-test (mean vs the runner-up) at alpha=0.05
    two-tailed.
  * If p < alpha AND minimum-sample-size thresholds clear AND the candidate
    is not the current baseline, recommend PROMOTE.
  * Otherwise: HOLD (with reason).

Why z-test instead of chi-square: with two groups it's equivalent and
the z-test gives a clean signed effect size + CI in one shot, which is
what the PR reader wants to see.

Calling convention
------------------
This is library code -- pure functions, no Flask, no I/O on the agent
hot path. The CLI command `sre-agent winner` wires this up + writes
output to stdout or a Markdown file.
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from sre_agent.feedback import STORE as FEEDBACK_STORE

# Verdicts we count as a "win". Both `thumbs_up` (general approval)
# and `correct` (oncall explicitly confirmed the root cause) → positive
# signal. Everything else (incl. blank corrections) is treated as a
# loss to keep the math honest.
POSITIVE_VERDICTS = {"thumbs_up", "correct"}


# ──────────────────────────────────────────────────────────────────────────
# Stats helpers -- small enough to avoid scipy as a dep
# ──────────────────────────────────────────────────────────────────────────


def wilson_interval(pos: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """
    Wilson score interval for a binomial proportion. Better than normal-
    approximation Wald especially when p is near 0 or 1, and trivially
    cheap. Returns (low, high) of the 95% CI when z=1.96.
    """
    if n == 0:
        return (0.0, 1.0)
    p = pos / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def two_prop_z(pos_a: int, n_a: int, pos_b: int, n_b: int) -> tuple[float, float]:
    """
    Standard two-proportion z-test. Returns (z_stat, two-sided p-value).
    Pools the variance under the null. Returns (0, 1.0) if either group
    has n=0 -- we don't make stat claims about empty groups.
    """
    if n_a == 0 or n_b == 0:
        return (0.0, 1.0)
    p_a = pos_a / n_a
    p_b = pos_b / n_b
    pool = (pos_a + pos_b) / (n_a + n_b)
    se = math.sqrt(pool * (1 - pool) * (1 / n_a + 1 / n_b))
    if se == 0:
        return (0.0, 1.0)
    z = (p_a - p_b) / se
    # two-sided p-value via erf -- math.erf gives erf(x) on the half-normal,
    # so a two-tailed p for a |z| of `z` is 2*(1 - Phi(|z|)) where
    # Phi(x) = 0.5 * (1 + erf(x/√2)).
    p_value = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
    return (z, p_value)


# ──────────────────────────────────────────────────────────────────────────
# Public types
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class GroupStat:
    """One (agent, prompt_sha) cell, with its rate + CI."""
    agent: str
    prompt_sha: str
    n: int
    positives: int
    rate: float
    ci_low: float
    ci_high: float

    @classmethod
    def build(cls, agent: str, sha: str, n: int, pos: int) -> GroupStat:
        rate = (pos / n) if n else 0.0
        low, high = wilson_interval(pos, n)
        return cls(agent=agent, prompt_sha=sha, n=n, positives=pos,
                   rate=rate, ci_low=low, ci_high=high)


@dataclass
class Decision:
    """One agent's verdict: promote, hold, or no-data."""
    agent: str
    verdict: str             # "promote" | "hold" | "no_data"
    reason: str
    winner_sha: str | None
    runner_up_sha: str | None
    delta_pp: float          # winner_rate - runner_rate, in percentage points
    p_value: float
    z_stat: float
    groups: list[GroupStat] = field(default_factory=list)
    baseline_sha: str | None = None

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["groups"] = [asdict(g) for g in self.groups]
        return d


@dataclass
class WinnerReport:
    """Output of one analysis run, suitable for both JSON and Markdown."""
    generated_at_ms: int
    alpha: float
    min_per_group: int
    min_delta_pp: float
    decisions: list[Decision]

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at_ms": self.generated_at_ms,
            "alpha": self.alpha,
            "min_per_group": self.min_per_group,
            "min_delta_pp": self.min_delta_pp,
            "decisions": [d.as_dict() for d in self.decisions],
        }

    def to_markdown(self) -> str:
        return _render_markdown(self)


# ──────────────────────────────────────────────────────────────────────────
# Core analysis
# ──────────────────────────────────────────────────────────────────────────


def aggregate_feedback(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, list[int]]]:
    """
    Walks raw feedback records and returns:
        { agent: { prompt_sha: [n, positives] } }

    Each "record" is the dict shape emitted by FeedbackStore.list_recent()
    (one record per oncall verdict, can be many per incident).

    Records without a `prompt_shas_seen` map are ignored -- we can't
    attribute them.
    """
    out: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for rec in records:
        verdict = rec.get("verdict")
        shas = rec.get("prompt_shas_seen") or {}
        if not shas:
            continue
        is_pos = verdict in POSITIVE_VERDICTS
        for agent, sha in shas.items():
            if not sha:
                continue
            cell = out[agent][sha]
            cell[0] += 1
            if is_pos:
                cell[1] += 1
    return out


def load_all_feedback() -> list[dict[str, Any]]:
    """
    Pulls every individual feedback record from the on-disk store. The
    store groups records by incident_id; we flatten that here because
    winner-promotion math doesn't care about incident boundaries.
    """
    flat: list[dict[str, Any]] = []
    for blob in FEEDBACK_STORE.list_recent(limit=100_000):
        flat.extend(blob.get("records") or [])
    return flat


def analyze(
    *,
    records: Iterable[dict[str, Any]] | None = None,
    baselines: dict[str, str] | None = None,
    alpha: float = 0.05,
    min_per_group: int = 50,
    min_delta_pp: float = 3.0,
) -> WinnerReport:
    """
    Run the winner analysis over the feedback corpus.

    `baselines` maps agent → current production prompt_sha. If a variant
    beats this baseline, we recommend PROMOTE. Without it, we still
    surface the best group + its CI but call it `hold` (no baseline to
    promote against).

    Thresholds:
      * `alpha` -- significance level for the z-test (0.05 default).
      * `min_per_group` -- minimum sample size per arm; below this the
        verdict is `hold` regardless of the point estimate.
      * `min_delta_pp` -- minimum point-estimate delta; below this we
        hold even if the p-value clears. This is a guardrail against
        promoting differences that are statistically real but
        practically meaningless ("p=0.04 from 50,000 records, delta
        0.4pp" doesn't move the needle in prod).
    """
    if records is None:
        records = load_all_feedback()
    if baselines is None:
        baselines = {}

    agg = aggregate_feedback(records)
    decisions: list[Decision] = []

    for agent, groups in agg.items():
        # No data path -- happens when an agent has been launched but no
        # variants have produced rated outputs yet.
        if not groups:
            decisions.append(Decision(
                agent=agent, verdict="no_data",
                reason="no feedback records carry this agent's prompt_sha",
                winner_sha=None, runner_up_sha=None,
                delta_pp=0.0, p_value=1.0, z_stat=0.0,
                baseline_sha=baselines.get(agent),
            ))
            continue

        stats = sorted(
            (GroupStat.build(agent, sha, *vals) for sha, vals in groups.items()),
            key=lambda s: -s.rate,
        )
        baseline_sha = baselines.get(agent)

        # Single-arm case: no A/B running, so there's no "winner" to
        # pick. We still emit the GroupStat for visibility but verdict
        # is hold/no_data.
        if len(stats) == 1:
            only = stats[0]
            decisions.append(Decision(
                agent=agent,
                verdict="hold",
                reason="only one prompt variant has feedback -- A/B not running",
                winner_sha=only.prompt_sha,
                runner_up_sha=None,
                delta_pp=0.0,
                p_value=1.0,
                z_stat=0.0,
                groups=stats,
                baseline_sha=baseline_sha,
            ))
            continue

        winner = stats[0]
        runner = stats[1]
        delta_pp = (winner.rate - runner.rate) * 100.0
        z, p = two_prop_z(winner.positives, winner.n, runner.positives, runner.n)

        # Thresholds: hold if any of (sample too small, delta too small,
        # p-value above alpha) fails. Order matters for the reason text.
        if min(winner.n, runner.n) < min_per_group:
            decisions.append(Decision(
                agent=agent,
                verdict="hold",
                reason=(
                    f"insufficient sample size -- need ≥{min_per_group} per arm "
                    f"(have winner={winner.n}, runner-up={runner.n})"
                ),
                winner_sha=winner.prompt_sha, runner_up_sha=runner.prompt_sha,
                delta_pp=delta_pp, p_value=p, z_stat=z, groups=stats,
                baseline_sha=baseline_sha,
            ))
            continue

        if delta_pp < min_delta_pp:
            decisions.append(Decision(
                agent=agent,
                verdict="hold",
                reason=(
                    f"point-estimate delta {delta_pp:+.1f}pp below min_delta_pp"
                    f" {min_delta_pp}pp"
                ),
                winner_sha=winner.prompt_sha, runner_up_sha=runner.prompt_sha,
                delta_pp=delta_pp, p_value=p, z_stat=z, groups=stats,
                baseline_sha=baseline_sha,
            ))
            continue

        if p >= alpha:
            decisions.append(Decision(
                agent=agent,
                verdict="hold",
                reason=(
                    f"not significant at alpha={alpha} (p={p:.3f}, z={z:+.2f}) -- "
                    "collect more data"
                ),
                winner_sha=winner.prompt_sha, runner_up_sha=runner.prompt_sha,
                delta_pp=delta_pp, p_value=p, z_stat=z, groups=stats,
                baseline_sha=baseline_sha,
            ))
            continue

        # If the winning sha IS the baseline, the "winner" is the
        # incumbent -- no action needed.
        if baseline_sha and winner.prompt_sha == baseline_sha:
            decisions.append(Decision(
                agent=agent,
                verdict="hold",
                reason=(
                    f"baseline {baseline_sha} is still the best -- "
                    f"+{delta_pp:.1f}pp over {runner.prompt_sha}, p={p:.3f}"
                ),
                winner_sha=winner.prompt_sha, runner_up_sha=runner.prompt_sha,
                delta_pp=delta_pp, p_value=p, z_stat=z, groups=stats,
                baseline_sha=baseline_sha,
            ))
            continue

        # All gates passed → promote.
        decisions.append(Decision(
            agent=agent,
            verdict="promote",
            reason=(
                f"variant {winner.prompt_sha} beats {runner.prompt_sha} by "
                f"{delta_pp:+.1f}pp at p={p:.3f} (n={winner.n} vs {runner.n})"
            ),
            winner_sha=winner.prompt_sha, runner_up_sha=runner.prompt_sha,
            delta_pp=delta_pp, p_value=p, z_stat=z, groups=stats,
            baseline_sha=baseline_sha,
        ))

    decisions.sort(key=lambda d: d.agent)
    return WinnerReport(
        generated_at_ms=int(time.time() * 1000),
        alpha=alpha,
        min_per_group=min_per_group,
        min_delta_pp=min_delta_pp,
        decisions=decisions,
    )


# ──────────────────────────────────────────────────────────────────────────
# Markdown rendering -- what an oncall sees in a PR description
# ──────────────────────────────────────────────────────────────────────────


def _render_markdown(report: WinnerReport) -> str:
    n_promote = sum(1 for d in report.decisions if d.verdict == "promote")
    n_hold = sum(1 for d in report.decisions if d.verdict == "hold")
    n_nodata = sum(1 for d in report.decisions if d.verdict == "no_data")

    lines = [
        "# Prompt A/B winner report",
        "",
        f"Generated at `{report.generated_at_ms}` (UTC ms).",
        "",
        "## Summary",
        "",
        f"- **{n_promote}** agent(s) recommended for promotion",
        f"- **{n_hold}** agent(s) holding (insufficient evidence)",
        f"- **{n_nodata}** agent(s) with no data",
        "",
        "## Decision thresholds",
        "",
        "| Threshold       | Value         |",
        "| --------------- | ------------- |",
        f"| alpha (two-tailed)  | {report.alpha} |",
        f"| min per group   | {report.min_per_group} |",
        f"| min delta       | {report.min_delta_pp}pp |",
        "",
        "## Per-agent decisions",
        "",
    ]

    for d in report.decisions:
        emoji = {"promote": "✅", "hold": "⏸", "no_data": "--"}[d.verdict]
        lines.append(f"### {emoji} `{d.agent}` -- **{d.verdict}**")
        lines.append("")
        lines.append(f"> {d.reason}")
        lines.append("")
        if d.groups:
            lines.append("| prompt_sha | n | positives | rate | 95% CI |")
            lines.append("| ---------- | - | --------- | ---- | ------ |")
            for g in d.groups:
                marker = ""
                if d.baseline_sha and g.prompt_sha == d.baseline_sha:
                    marker = " *(baseline)*"
                if d.verdict == "promote" and g.prompt_sha == d.winner_sha:
                    marker = " **(winner)**"
                lines.append(
                    f"| `{g.prompt_sha}`{marker} | {g.n} | {g.positives} | "
                    f"{g.rate:.3f} | [{g.ci_low:.3f}, {g.ci_high:.3f}] |"
                )
            lines.append("")
        if d.verdict == "promote":
            lines.append(
                f"**Action**: copy `personas/variants/{d.agent}-…md` over "
                f"`personas/{d.agent}.md`, bump prompt_sha, redeploy."
            )
            lines.append("")

    return "\n".join(lines) + "\n"


# Convenience for the CLI: also dump JSON for machine readers.
def to_json(report: WinnerReport, *, indent: int = 2) -> str:
    return json.dumps(report.as_dict(), indent=indent)
