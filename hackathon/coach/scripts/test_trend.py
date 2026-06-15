import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trend  # noqa: E402


class TrendTests(unittest.TestCase):
    def test_iso_week_key(self):
        self.assertEqual(trend.iso_week("2026-06-01T10:00:00Z"), "2026-W23")

    def test_two_weeks_produce_deltas(self):
        dated = [
            {"week": "2026-W22", "scores": {"outcomes": 6.0}, "confidence": 1.0},
            {"week": "2026-W24", "scores": {"outcomes": 8.0}, "confidence": 1.0},
        ]
        out = trend.build(dated)
        self.assertEqual(len(out["weeks"]), 2)
        self.assertAlmostEqual(out["deltas"]["outcomes"], 2.0, places=2)
        self.assertIsNone(out.get("note"))

    def test_single_week_suppresses_trend(self):
        dated = [{"week": "2026-W22", "scores": {"outcomes": 6.0}, "confidence": 1.0}]
        out = trend.build(dated)
        self.assertEqual(len(out["weeks"]), 1)
        self.assertIsNone(out["deltas"])
        self.assertIn("not enough time span", out["note"])

    def test_date_episodes_uses_real_gitdata_session_ids(self):
        episodes = [{"episode_id": 1, "scores": {"outcomes": 7.0}, "confidence": 1.0}]
        sessions = [{"session_id": "s1", "session_created_at": "2026-06-01T10:00:00Z"}]
        gitdata = {"episodes": [{"episode_id": 1, "session_ids": ["s1"]}]}
        dated = trend._date_episodes(episodes, sessions, gitdata)
        self.assertEqual(len(dated), 1)
        self.assertEqual(dated[0]["week"], "2026-W23")

    def test_date_episodes_falls_back_to_links(self):
        episodes = [{"episode_id": 2, "scores": {"outcomes": 7.0}, "confidence": 1.0}]
        sessions = [{"session_id": "s2", "session_created_at": "2026-06-01T10:00:00Z"}]
        gitdata = {"episodes": [{"episode_id": 2, "links": [{"session_id": "s2"}]}]}
        dated = trend._date_episodes(episodes, sessions, gitdata)
        self.assertEqual(len(dated), 1)
        self.assertEqual(dated[0]["week"], "2026-W23")


if __name__ == "__main__":
    unittest.main()
