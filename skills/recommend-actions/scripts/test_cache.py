import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import cache

CANDS = [{"family": "acquire", "title": "Add the GitHub MCP server",
          "source": {"kind": "live_web", "url": "https://example.com/gh",
                     "freshness": "2026-06-15"}}]


def test_cache_path_is_in_profile_dir():
    assert cache.cache_path("/p").endswith("capabilities_cache.json")
    assert cache.cache_path("/p").startswith("/p")


def test_load_cache_absent_returns_none(tmp_path):
    assert cache.load_cache(str(tmp_path)) is None


def test_write_then_load_roundtrip(tmp_path):
    cache.write_cache(str(tmp_path), CANDS, "2026-06-01T00:00:00+00:00", True,
                      now_iso="2026-06-15T00:00:00+00:00")
    c = cache.load_cache(str(tmp_path))
    assert c["candidates"] == CANDS
    assert c["profile_generated_at"] == "2026-06-01T00:00:00+00:00"
    assert c["network_used"] is True
    assert c["fetched_at"] == "2026-06-15T00:00:00+00:00"


def test_is_fresh_true_within_ttl_and_matching_profile(tmp_path):
    cache.write_cache(str(tmp_path), CANDS, "2026-06-01T00:00:00+00:00", True,
                      now_iso="2026-06-10T00:00:00+00:00")
    c = cache.load_cache(str(tmp_path))
    # fetched 2026-06-10, now 2026-06-20 -> 10 days < 14, profile unchanged
    assert cache.is_fresh(c, "2026-06-01T00:00:00+00:00",
                          now_iso="2026-06-20T00:00:00+00:00") is True


def test_is_fresh_false_when_profile_regenerated(tmp_path):
    cache.write_cache(str(tmp_path), CANDS, "2026-06-01T00:00:00+00:00", True,
                      now_iso="2026-06-10T00:00:00+00:00")
    c = cache.load_cache(str(tmp_path))
    assert cache.is_fresh(c, "2026-06-09T00:00:00+00:00",   # different generated_at
                          now_iso="2026-06-11T00:00:00+00:00") is False


def test_is_fresh_false_when_aged_past_ttl(tmp_path):
    cache.write_cache(str(tmp_path), CANDS, "2026-06-01T00:00:00+00:00", True,
                      now_iso="2026-06-01T00:00:00+00:00")
    c = cache.load_cache(str(tmp_path))
    # fetched 2026-06-01, now 2026-06-20 -> 19 days > 14
    assert cache.is_fresh(c, "2026-06-01T00:00:00+00:00",
                          now_iso="2026-06-20T00:00:00+00:00") is False


def test_is_fresh_false_on_none_cache():
    assert cache.is_fresh(None, "x", now_iso="2026-06-20T00:00:00+00:00") is False


def test_status_cli_reports_fresh(tmp_path):
    cache.write_cache(str(tmp_path), CANDS, "2026-06-01T00:00:00+00:00", True,
                      now_iso="2026-06-10T00:00:00+00:00")
    out = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "cache.py"),
         "status", str(tmp_path), "--profile-generated-at", "2026-06-01T00:00:00+00:00",
         "--now", "2026-06-15T00:00:00+00:00"],
        capture_output=True, text=True, check=True).stdout
    doc = json.loads(out)
    assert doc["exists"] is True and doc["fresh"] is True and doc["count"] == 1


def test_status_cli_reports_absent(tmp_path):
    out = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "cache.py"),
         "status", str(tmp_path), "--profile-generated-at", "2026-06-01T00:00:00+00:00",
         "--now", "2026-06-15T00:00:00+00:00"],
        capture_output=True, text=True, check=True).stdout
    doc = json.loads(out)
    assert doc["exists"] is False and doc["fresh"] is False and doc["count"] == 0


def test_write_cli_persists_candidates(tmp_path):
    cfile = tmp_path / "cands.json"
    cfile.write_text(json.dumps(CANDS))
    out = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "cache.py"),
         "write", str(tmp_path), str(cfile),
         "--profile-generated-at", "2026-06-01T00:00:00+00:00",
         "--network-used", "--now", "2026-06-15T00:00:00+00:00"],
        capture_output=True, text=True, check=True).stdout
    assert json.loads(out)["count"] == 1
    assert cache.load_cache(str(tmp_path))["network_used"] is True
