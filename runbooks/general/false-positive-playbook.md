# False-positive alert playbook

Most pages are not real incidents. This is the checklist that tells you
when to stand down without rolling anything back.

## When to declare a false positive

> tags: false-positive, noise, alert-tuning

All of these must be true:

- **Logs**: error rate is at or near baseline (within 2x of usual noise)
- **Metrics**: no metric is sustainably elevated (a 1-min blip is not a
  signal; a 5-min sustained ridge is)
- **Traces**: no anomalous hot span; no error_rate elevation in the
  trace sample
- **Deploys**: either no deploys in the window, OR the deploy was hours
  ago and other services that consume the same change are fine

If even **one** pillar shows clear deviation, hold off declaring false
positive for 10 more minutes and re-check.

## What to do about it

> tags: alert-tuning, postmortem

1. Mark the incident "resolved — false positive" in the dashboard.
2. File a follow-up to tune the alert threshold. Common fixes:
   - Add hysteresis (require N consecutive samples above threshold)
   - Switch from absolute to relative threshold (e.g. p99 > 3× rolling
     1-hour median, rather than p99 > 500ms hard-coded)
   - Exclude noisy endpoints (`/slow`, `/health`, synthetic probes) from
     the SLO that drives the alert
3. **Do not silently snooze.** That just means the next false positive
   will wake someone up at 3am with the same flawed threshold.

## Why this matters

> tags: oncall-health

Alert fatigue is the #1 reason real outages get missed. Every false
positive that goes un-tuned is a small tax on your team's trust in the
alerting system. Treat tuning as part of incident response, not a "we
should get to that eventually" backlog item.
