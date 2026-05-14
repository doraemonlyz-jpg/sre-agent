# ADR-006: No autonomous execution of remediations

- **Status:** Accepted
- **Date:** 2026-04-15

## Context

The remediation suggester emits concrete shell / kubectl commands
("kubectl rollout undo deployment/checkout-api"). It would be
technically straightforward to wire those into a Kubernetes client
and have the agent execute them autonomously when confidence is
high.

We deliberately do NOT do this.

## Decision

The agent only ever **proposes** remediations. Execution requires
a human to copy-paste the command into a terminal (or click a button
in a future "approve & execute" UI that is on the roadmap but
explicitly behind a separate ADR).

The dashboard renders remediation actions with a "Copy command"
button, never a "Run" button.

## Considered

- **Auto-execute when confidence > 0.95.** Two reasons against:
  1. The confidence is the LLM's estimate; we know from
     [ADR-004](./004-fallback-chain.md) and the calibrator work
     that LLM confidence is systematically miscalibrated upward.
     Treating it as a fitness function for "should I act" is
     compounding model error with operational risk.
  2. The remediation set includes "rollback prod deploy" and
     "drain a Kubernetes node". The blast radius of a wrong action
     is permanently larger than the cost of a 30-second human
     review.
- **Auto-execute behind a feature flag, off by default.** Even
  off-by-default, it's a footgun in a repo people will fork. We
  prefer a separate, named branch that opts in to that risk
  posture.

## Consequences

- **Good:** the worst the agent can do is write the wrong text into
  Slack / PagerDuty. No prod-mutating verbs.
- **Good:** the human reviewer is a forcing function for noticing
  obviously-wrong suggestions, which doubles as feedback into the
  L6 flywheel.
- **Bad:** time-to-mitigate is bounded below by human reaction time
  (~30s). For SEV-1s where every minute is revenue, that's a real
  cost. We accept it.
- **Bad:** every remediation needs to be a complete shell command
  the human can run verbatim, not a pseudo-code sketch. Documented
  in the persona for `remediation-suggester`.
