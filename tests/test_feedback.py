"""
Tests for the feedback store (the substrate for the L5 flywheel).
"""

from __future__ import annotations

import json

import pytest

from sre_agent.feedback import STORE, VALID_VERDICTS, make_record


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("SRE_FEEDBACK_DIR", str(tmp_path))
    STORE.reset()
    yield
    STORE.reset()


class TestMakeRecord:
    def test_minimal_thumbs_up(self):
        r = make_record(verdict="thumbs_up")
        assert r.verdict == "thumbs_up"
        assert r.id.startswith("fb-")
        assert r.submitter == "anon"

    def test_invalid_verdict_raises(self):
        with pytest.raises(ValueError):
            make_record(verdict="🤷")

    def test_invalid_rating_raises(self):
        with pytest.raises(ValueError):
            make_record(verdict="thumbs_up", rating=10)

    def test_rating_at_bounds_ok(self):
        for r in (1, 5):
            assert make_record(verdict="thumbs_up", rating=r).rating == r


class TestAppendGet:
    def test_append_then_get(self):
        rec = make_record(verdict="thumbs_up", submitter="alice")
        STORE.append("inc-1", rec)
        blob = STORE.get("inc-1")
        assert blob is not None
        assert blob["incident_id"] == "inc-1"
        assert len(blob["records"]) == 1
        assert blob["records"][0]["submitter"] == "alice"

    def test_get_missing_returns_none(self):
        assert STORE.get("never-existed") is None

    def test_append_is_idempotent_in_shape(self):
        """Two appends to the same incident produce two records, not a clobber."""
        STORE.append("inc-1", make_record(verdict="thumbs_up"))
        STORE.append("inc-1", make_record(verdict="thumbs_down"))
        blob = STORE.get("inc-1")
        verdicts = [r["verdict"] for r in blob["records"]]
        assert verdicts == ["thumbs_up", "thumbs_down"]


class TestSummary:
    def test_empty_summary(self):
        s = STORE.summary()
        assert s["total"] == 0
        assert s["csat"] is None

    def test_csat_math(self):
        for v in ["thumbs_up", "thumbs_up", "thumbs_down", "correct"]:
            STORE.append("inc-x", make_record(verdict=v))
        STORE._totals_loaded = False  # force re-aggregation from disk
        s = STORE.summary()
        # 3 positive (thumbs_up x2, correct x1), 1 negative
        assert s["positive"] == 3
        assert s["negative"] == 1
        assert s["total"] == 4
        assert s["csat"] == 0.75

    def test_invalid_verdict_never_lands_in_counter(self):
        """Defense in depth: even if disk gets a bad record, summary survives."""
        rec = make_record(verdict="thumbs_up")
        STORE.append("inc-1", rec)
        # Manually inject a bad record on disk
        from sre_agent.feedback import _feedback_dir

        path = _feedback_dir() / "inc-1.json"
        blob = json.loads(path.read_text("utf-8"))
        blob["records"].append({"id": "bad", "verdict": "explode"})
        path.write_text(json.dumps(blob))

        STORE._totals_loaded = False
        s = STORE.summary()
        # Only the valid one is counted
        assert s["counters"]["thumbs_up"] == 1


class TestListRecent:
    def test_list_recent_orders_by_mtime(self):
        import time

        STORE.append("a", make_record(verdict="thumbs_up"))
        time.sleep(0.01)
        STORE.append("b", make_record(verdict="thumbs_up"))
        recents = STORE.list_recent(limit=10)
        ids = [r["incident_id"] for r in recents]
        assert ids[0] == "b"
        assert "a" in ids


class TestValidVerdictsContract:
    def test_known_verdicts_locked(self):
        assert set(VALID_VERDICTS) == {"thumbs_up", "thumbs_down", "correct", "incorrect"}
