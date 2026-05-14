<!--
Thanks for the contribution! Please fill in the sections that apply.
Trim sections that don't.

If this PR was opened by a GitHub Action (harness-winner or harness-autorunbook),
the bot will already have populated the body with the report. Reviewers should
focus on the "Reviewer checklist" below.
-->

## What & why

<!-- 1–3 sentences. What does this change? Why is it needed? -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor (no behaviour change)
- [ ] Persona / prompt change (model behaviour)
- [ ] Runbook addition or edit (knowledge base)
- [ ] **Auto-promoted prompt variant** (opened by `harness-winner`)
- [ ] **Auto-drafted runbook** (opened by `harness-autorunbook`)
- [ ] **Auto-refit calibrator** (opened by `harness-calibration`)
- [ ] Tooling / CI / infra
- [ ] Docs only

## How to review

<!-- Walk the reviewer through the diff. What should they look at first?
     Are there commits worth splitting up? -->

## Test plan

<!-- For code changes: how did you verify this works?
     - Unit tests added / updated?
     - Demo script run? (paste a screenshot or trimmed log)
     - Manual dashboard verification? -->

## Reviewer checklist

Standard items:

- [ ] CI is green (pytest + ruff)
- [ ] Changes match the description; nothing unrelated snuck in
- [ ] Public API / data-contract changes are documented
- [ ] Logging / metrics / traces still cover the new path

**For persona changes (`personas/**.md`):**

- [ ] Diff has been read line-by-line — prompts are load-bearing
- [ ] If this is an auto-promoted variant, the winner report below
      shows: delta ≥ `MIN_DELTA_PP` (default 3pp), p < 0.05, and N ≥
      `MIN_SAMPLES` (default 50) per arm
- [ ] We're prepared to **roll back** by reverting this PR if oncall
      thumbs-down rate jumps in the 24h after merge
- [ ] No prompt injection / no secrets / no PII templates

**For runbook changes (`runbooks/**.md`):**

- [ ] Service team owning the impacted service has approved
- [ ] If this is an auto-drafted runbook, the "agent-vs-oncall"
      contradictions below have been spot-checked against the source
      incidents (sample 2–3 cited incident IDs)
- [ ] The remediation procedure has been validated in staging (or has
      an explicit "DRAFT — needs validation" tag)

**For GHA / automation changes (`.github/**`, `scripts/**`):**

- [ ] No new outbound tokens / secrets exposed in logs
- [ ] Workflow `permissions:` block is as narrow as it can be
- [ ] `concurrency:` is set if the workflow opens PRs (avoid stampede)
- [ ] Dry-run / local-debug instructions added to the script's header

## Auto-bot reports

<!--
The harness-winner and harness-autorunbook bots populate the section
below automatically. Leave it empty for human-authored PRs.
-->

<!-- bot-report-start -->
<!-- bot-report-end -->

## Linked issues

<!-- Closes #123 / Refs #456 / N/A -->
