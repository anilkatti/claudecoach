import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import build_indexes as bi


def test_normalize_practice_requires_source_url():
    assert bi.normalize_practice({"id": "p1", "principle": "plan first"}) is None
    ok = bi.normalize_practice(
        {"id": "p1", "principle": "plan first", "applies_to_signal": "planning",
         "source_url": "https://platform.claude.com/x", "source_org": "anthropic"})
    assert ok["id"] == "p1"


def test_merge_dedupes_by_key():
    merged = bi.merge_by_key(
        [{"id": "a", "source_url": "u1"}],
        [{"id": "a", "source_url": "u2"}], keys=("id",))
    assert len(merged) == 1 and merged[0]["source_url"] == "u2"  # fetched wins


def test_build_practices_drops_failing_source_and_records_it():
    def fetch(src):
        if src == "bad":
            raise RuntimeError("boom")
        return [{"id": "ok", "principle": "p", "applies_to_signal": "planning",
                 "source_url": "https://e.com/ok", "source_org": "anthropic"}]
    doc = bi.build_practices(["good", "bad"], fetch, now_iso="2026-06-10T00:00:00+00:00")
    assert doc["built_at"] == "2026-06-10T00:00:00+00:00"
    assert [p["id"] for p in doc["practices"]] == ["ok"]
    assert any("bad" in d for d in doc["dropped"])


def test_capabilities_index_building_is_removed():
    # capabilities are researched live + cached now (see cache.py), not built into a
    # static index — these functions must be gone. Mirrors test_apply's no-delete guard.
    assert not hasattr(bi, "build_capabilities")
    assert not hasattr(bi, "normalize_capability")
