"""
Tests for the synthetic data seeder.

These are the only tests in the repo that have to defend two things at
once:

  (1) The seeder's output is a CORRECT, well-typed substitute for real
      production data -- the same `FeedbackStore.append()` shape, the
      same `LLMCallRecord` field set, no surprise nulls. If we break
      this we silently break the L6 features that read it back.

  (2) The seeder's distributions are still INFORMATIVE. The whole
      point is that downstream readers can learn from the data. So we
      test that the variant arm has a meaningfully higher thumbs-up
      rate than the baseline arm at "production-realistic" sample
      sizes.

We use deterministic seed values throughout -- flaky stats tests are an
anti-pattern (they erode confidence in CI and end up being deleted).
"""

from __future__ import annotations

import pytest

from sre_agent.feedback import STORE as FEEDBACK_STORE
from sre_agent.harness import RECORDER
from sre_agent.seed import seed


@pytest.fixture(autouse=True)
def _isolated_feedback_dir(tmp_path, monkeypatch):
    """Every test gets its own feedback dir. Without this, the file-
    backed store leaks across tests and the assertions become a function
    of test order."""
    monkeypatch.setenv("SRE_FEEDBACK_DIR", str(tmp_path / "feedback"))
    FEEDBACK_STORE.reset()
    yield
    FEEDBACK_STORE.reset()


def test_smoke_small_n_runs_to_completion():
    """50 incidents seed in under a second and return a coherent summary."""
    result = seed(n=50, seed_value=42)
    assert result.n_incidents == 50
    # Feedback isn't guaranteed for every incident (75% review rate) so
    # bound loosely.
    assert 10 <= result.n_feedback <= 50
    assert result.n_llm_records > 0
    assert result.duration_s < 5.0


def test_determinism_same_seed_same_counts():
    """Same RNG seed → same output counts. The actual records don't
    have stable IDs (UUIDs), but distributions are reproducible."""
    a = seed(n=200, seed_value=42)
    b = seed(n=200, seed_value=42)
    assert a.n_incidents == b.n_incidents
    assert a.n_feedback == b.n_feedback
    assert a.n_llm_records == b.n_llm_records
    assert a.n_cache_hits == b.n_cache_hits


def test_different_seeds_produce_different_outputs():
    """Sanity: the seed actually drives the RNG. Otherwise we'd be
    silently generating identical demos every time."""
    a = seed(n=200, seed_value=1)
    b = seed(n=200, seed_value=99)
    # Identical n_incidents is fine; the rest should vary.
    assert (a.n_feedback, a.n_llm_records, a.n_cache_hits) != \
           (b.n_feedback, b.n_llm_records, b.n_cache_hits)


def test_feedback_records_carry_prompt_shas():
    """Without `prompt_shas_seen`, the winner cron has nothing to join
    on. This is the load-bearing contract."""
    seed(n=200, seed_value=42)
    blobs = FEEDBACK_STORE.list_recent(limit=1000)
    assert blobs, "seed produced no feedback blobs"
    with_shas = 0
    for blob in blobs:
        for rec in blob.get("records", []):
            if rec.get("prompt_shas_seen"):
                with_shas += 1
    assert with_shas > 0, "no feedback record carried prompt_shas_seen"


def test_feedback_alert_snapshot_persisted():
    """L6 autorunbook reads this -- break it and the drafter sees zero
    clusters even with thousands of corrections."""
    seed(n=200, seed_value=42)
    blobs = FEEDBACK_STORE.list_recent(limit=1000)
    blobs_with_alert = [b for b in blobs if b.get("alert")]
    assert blobs_with_alert, "no blob carried an alert snapshot"
    sample = blobs_with_alert[0]["alert"]
    assert "service" in sample and "description" in sample


def test_variant_signal_present_at_n_2000():
    """
    The whole point of the seeded data is that the variant arm beats
    the baseline arm. At N=2000 with 20% A/B traffic we expect a
    positive delta with high probability.

    After the B3 confidence-shift logic was wired in, the effective
    delta drops a couple of points (baseline has higher confidence,
    which is itself a weak positive predictor and partially cancels
    the variant's pure algorithmic edge). The 3pp threshold here is
    chosen well below the empirical mean (+5 to +7pp) but well above
    the null (0pp) so a true signal regression still trips the test.
    """
    seed(n=2000, seed_value=42, ab_fraction=0.2)
    blobs = FEEDBACK_STORE.list_recent(limit=10_000)
    sha_counts = {}
    for blob in blobs:
        for rec in blob.get("records", []):
            sha = (rec.get("prompt_shas_seen") or {}).get("hypothesis-gen")
            if not sha:
                continue
            sha_counts.setdefault(sha, [0, 0])
            sha_counts[sha][0] += 1
            if rec.get("verdict") in ("thumbs_up", "correct"):
                sha_counts[sha][1] += 1

    baseline = sha_counts.get("0c8f14d5")
    variant = sha_counts.get("9a4e2b73")
    assert baseline and variant, f"missing arms: {sha_counts.keys()}"
    base_rate = baseline[1] / baseline[0]
    var_rate = variant[1] / variant[0]
    assert var_rate - base_rate > 0.03, (
        f"variant signal too weak: baseline={base_rate:.3f} variant={var_rate:.3f}"
    )


def test_harness_records_have_required_fields():
    """The recorder feeds /api/harness -- if we silently drop fields,
    the dashboard panel breaks."""
    seed(n=50, seed_value=42)
    records = RECORDER.recent(limit=10_000)
    llm = [r for r in records if r.kind == "llm_call"]
    assert llm, "no llm_call records produced"
    sample = llm[0]
    assert sample.agent
    assert sample.prompt_sha
    assert sample.latency_ms > 0
    assert sample.input_tokens > 0
    assert sample.status in ("ok", "error")


def test_cache_hits_attributed_to_harness_agent():
    """Cache-hit records should be tagged `agent="harness"` so the
    harness summary's by_agent count is meaningful."""
    seed(n=500, seed_value=42)
    records = RECORDER.recent(limit=10_000)
    cache_hits = [r for r in records if r.kind == "cache_hit"]
    if cache_hits:  # tolerate the unlikely zero-cache-hit run
        assert all(r.agent == "harness" for r in cache_hits)


def test_reset_first_true_clears_prior_state():
    """First call seeds, second call (reset_first=True) replaces. We
    must not see double-counting."""
    seed(n=100, seed_value=42)
    first_total = FEEDBACK_STORE.summary()["total"]
    assert first_total > 0
    seed(n=100, seed_value=42, reset_first=True)
    second_total = FEEDBACK_STORE.summary()["total"]
    # Total should approximate the first run, not double it.
    assert second_total < first_total * 1.5


def test_n_zero_is_a_no_op():
    """Edge case: n=0 should not crash and should produce zero output."""
    result = seed(n=0, seed_value=42)
    assert result.n_incidents == 0
    assert result.n_feedback == 0
    assert result.n_llm_records == 0
