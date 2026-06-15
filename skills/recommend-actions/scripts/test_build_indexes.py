import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import build_indexes as bi


def test_normalize_capability_ok():
    out = bi.normalize_capability(
        {"name": "pr-triage", "kind": "skill", "source": "marketplace",
         "one_liner": "Triage PRs", "when_to_use": "many PRs", "tags": ["git"],
         "url": "https://example.com/pr-triage"})
    assert out["name"] == "pr-triage" and out["url"].startswith("https://")


def test_normalize_capability_without_url_is_rejected():
    assert bi.normalize_capability({"name": "x", "kind": "skill"}) is None


def test_normalize_practice_requires_source_url():
    assert bi.normalize_practice({"id": "p1", "principle": "plan first"}) is None
    ok = bi.normalize_practice(
        {"id": "p1", "principle": "plan first", "applies_to_signal": "planning",
         "source_url": "https://platform.claude.com/x", "source_org": "anthropic"})
    assert ok["id"] == "p1"


def test_merge_dedupes_by_key():
    merged = bi.merge_by_key(
        [{"name": "a", "kind": "skill", "url": "u1"}],
        [{"name": "a", "kind": "skill", "url": "u2"}], keys=("name", "kind"))
    assert len(merged) == 1 and merged[0]["url"] == "u2"  # fetched wins


def test_build_drops_failing_source_and_records_it():
    def fetch(src):
        if src == "bad":
            raise RuntimeError("boom")
        return [{"name": "ok", "kind": "skill", "source": "s", "one_liner": "",
                 "when_to_use": "", "tags": [], "url": "https://e.com/ok"}]
    doc = bi.build_capabilities(["good", "bad"], fetch, now_iso="2026-06-10T00:00:00+00:00")
    assert doc["built_at"] == "2026-06-10T00:00:00+00:00"
    assert [c["name"] for c in doc["capabilities"]] == ["ok"]
    assert any("bad" in d for d in doc["dropped"])
