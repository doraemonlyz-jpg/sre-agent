"""
Tests for the prompt A/B routing in personas.py.

Locked-in contract:

  * `load()` and the no-A/B `load_with_sha()` path always return baseline.
  * `SRE_PROMPT_VARIANT_<AGENT>=name` pins every call to that variant.
  * `SRE_PROMPT_AB_<AGENT>=name:0` means 0% to variant (always baseline).
  * `SRE_PROMPT_AB_<AGENT>=name:1` means 100% to variant.
  * A missing variant file silently falls back to baseline (no exception).
"""

from __future__ import annotations

import pytest

from sre_agent import personas


@pytest.fixture(autouse=True)
def clear_cache(monkeypatch):
    # We poke env, so wipe per-test caches that hold (file → bytes).
    personas._read.cache_clear()
    personas._read_file.cache_clear()
    monkeypatch.delenv("SRE_PROMPT_VARIANT_HYPOTHESIS_GEN", raising=False)
    monkeypatch.delenv("SRE_PROMPT_AB_HYPOTHESIS_GEN", raising=False)
    yield


class TestBaseline:
    def test_load_returns_baseline_text(self):
        text = personas.load("hypothesis-gen")
        assert "Hypothesis Generator" in text

    def test_load_with_sha_returns_baseline_when_no_routing(self):
        baseline_text, baseline_sha = personas._read("hypothesis-gen")
        text, sha = personas.load_with_sha("hypothesis-gen")
        assert sha == baseline_sha
        assert text == baseline_text


class TestPinnedVariant:
    def test_pinned_variant_used(self, monkeypatch):
        monkeypatch.setenv("SRE_PROMPT_VARIANT_HYPOTHESIS_GEN", "conservative")
        text, sha = personas.load_with_sha("hypothesis-gen")
        assert "CONSERVATIVE" in text
        _, baseline_sha = personas._read("hypothesis-gen")
        assert sha != baseline_sha

    def test_pinned_missing_variant_falls_back_silently(self, monkeypatch):
        monkeypatch.setenv("SRE_PROMPT_VARIANT_HYPOTHESIS_GEN", "does-not-exist")
        text, sha = personas.load_with_sha("hypothesis-gen")
        baseline_text, baseline_sha = personas._read("hypothesis-gen")
        # Should NOT crash. Should serve baseline.
        assert text == baseline_text
        assert sha == baseline_sha


class TestABRouting:
    def test_zero_fraction_always_baseline(self, monkeypatch):
        monkeypatch.setenv("SRE_PROMPT_AB_HYPOTHESIS_GEN", "conservative:0")
        baseline_text, _ = personas._read("hypothesis-gen")
        for _ in range(20):
            text, _ = personas.load_with_sha("hypothesis-gen")
            assert text == baseline_text

    def test_full_fraction_always_variant(self, monkeypatch):
        monkeypatch.setenv("SRE_PROMPT_AB_HYPOTHESIS_GEN", "conservative:1")
        for _ in range(20):
            text, _ = personas.load_with_sha("hypothesis-gen")
            assert "CONSERVATIVE" in text

    def test_partial_fraction_eventually_picks_both(self, monkeypatch):
        monkeypatch.setenv("SRE_PROMPT_AB_HYPOTHESIS_GEN", "conservative:0.5")
        seen_baseline = False
        seen_variant = False
        # 200 draws → P(missing either bucket) ≈ 0 for fair 50/50.
        for _ in range(200):
            text, _ = personas.load_with_sha("hypothesis-gen")
            if "CONSERVATIVE" in text:
                seen_variant = True
            else:
                seen_baseline = True
        assert seen_variant and seen_baseline

    def test_malformed_ab_falls_back(self, monkeypatch):
        monkeypatch.setenv("SRE_PROMPT_AB_HYPOTHESIS_GEN", "no-colon-here")
        baseline_text, _ = personas._read("hypothesis-gen")
        text, _ = personas.load_with_sha("hypothesis-gen")
        assert text == baseline_text


class TestListVariants:
    def test_lists_existing_variants(self):
        variants = personas.list_variants("hypothesis-gen")
        assert "conservative" in variants

    def test_no_variants_for_unknown_agent(self):
        assert personas.list_variants("nonexistent-agent") == []


class TestLoadSpecific:
    def test_baseline_when_none(self):
        text, sha = personas.load_specific("hypothesis-gen", variant_name=None)
        baseline_text, baseline_sha = personas._read("hypothesis-gen")
        assert text == baseline_text and sha == baseline_sha

    def test_missing_variant_raises(self):
        with pytest.raises(FileNotFoundError):
            personas.load_specific("hypothesis-gen", variant_name="ghost")

    def test_existing_variant_loaded(self):
        text, sha = personas.load_specific("hypothesis-gen", variant_name="conservative")
        assert "CONSERVATIVE" in text
        baseline_sha = personas._read("hypothesis-gen")[1]
        assert sha != baseline_sha
