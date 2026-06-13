import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coach_report as cr  # noqa: E402


class CoachReportTests(unittest.TestCase):
    def _ctx(self):
        return {
            "repo_name": "demo",
            "episodes": [
                {"episode_id": 1, "title": "Shipped a fix",
                 "what_it_shows": "Closes loops cleanly.", "confidence": 0.9,
                 "scores": {"outcomes": 8.0, "steering": 6.0, "quality": 7.0,
                            "planning": 6.0, "leverage": 5.0}}],
            "trend": {"weeks": [{"week": "2026-W22", "axes": {"outcomes": 6.0},
                                 "overall": 6.0, "n_episodes": 1}],
                      "deltas": None, "note": "not enough time span to show a trend yet"},
            "habits": {"habits": [{"key": "vague", "label": "short prompts",
                                   "polarity": "holding-you-back",
                                   "coaching": "add context",
                                   "evidence": "2 of 3 sessions"}]},
            "recommendations": {"recommend": [
                {"name": "writing-plans", "why": "breaks work into steps",
                 "helps_axis": "Thinking ahead"}], "reconsider": []},
            "index_built_at": "2026-06-13",
        }

    def test_render_has_all_sections_and_plain_band(self):
        md = cr.render(self._ctx())
        self.assertIn("Getting things done", md)          # plain axis name
        self.assertIn("Solid", md)                         # softened band (overall 6.4)
        self.assertIn("not enough time span", md)          # trend suppression
        self.assertIn("short prompts", md)                 # habit
        self.assertIn("writing-plans", md)                 # recommendation
        self.assertIn("Haiku", md)                         # honesty fine print
        self.assertNotIn("Execution Leverage", md)         # no engineering jargon


if __name__ == "__main__":
    unittest.main()
