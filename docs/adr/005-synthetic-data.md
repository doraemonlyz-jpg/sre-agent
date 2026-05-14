# ADR-005: Synthetic data for L6 self-improvement

- **Status:** Accepted
- **Date:** 2026-05-05

## Context

L6 -- the "self-improving flywheel" tier -- needs three signals
the system would normally collect from production:

1. Per-prompt-variant feedback (`thumbs_up` / `thumbs_down` from
   on-call).
2. Per-incident outcome (was the agent's hypothesis correct?
   `correct_root_cause` flag).
3. Predicted-vs-observed pairs for the confidence calibrator.

We don't have a production deployment with real on-call traffic.
Without those signals, the L6 features (winner promotion,
auto-runbook drafting, calibrator refit) have nothing to chew on
and we can't demonstrate or test them end-to-end.

## Decision

Implement a synthetic-data seeder (`src/sre_agent/seed.py`) that
generates a plausible feedback corpus with controlled distributions:

- N=2000 incidents across the existing scenarios.
- Two prompt variants (A and B), with B having a measurably better
  thumbs-up rate (~4 percentage points). Strong enough to detect
  with a Wilson-CI z-test, weak enough to be realistic.
- Confidence values that form a typical LLM-overconfidence curve
  (high-confidence buckets are ~10pp less accurate than they claim
  to be), so the isotonic calibrator has something useful to fit.
- `no_signal` and `timeout` phases excluded from calibration data
  so the smoke tests aren't dominated by abstentions.

The seeder is gated behind `SRE_SEED_ON_BOOT=true`. Production runs
never invoke it; CI and the L6 cron jobs set it explicitly via
`scripts/run-calibration-job.py`.

## Considered

- **Wait for real production data.** Not an option -- the author
  has no production deployment.
- **Hand-craft 50 feedback rows.** Too small for the statistical
  tests (Wilson CIs would all overlap; calibrator would overfit).
- **Replay anonymised public incident postmortems.** Interesting
  but each postmortem is one row, not the thousands needed.

## Consequences

- **Good:** L6 features can be demonstrated end-to-end, including
  the GitHub Actions workflows that open PRs based on the synthetic
  feedback.
- **Good:** the seeder is itself a behavioural specification of what
  "good production data should look like". When real data arrives,
  drift between real distribution and synthetic distribution is its
  own diagnostic signal.
- **Bad:** every L6 result is implicitly conditional on the seeder's
  assumptions. We document this prominently in `docs/index.html` and
  in `scripts/run-calibration-job.py`'s help output.
- **Bad:** running tests with the seeder enabled adds ~3s; we keep
  it opt-in and gate the L6 unit tests behind their own marker.
