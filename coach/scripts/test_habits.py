import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import habits  # noqa: E402

CATALOG = {"habits": [
    {"key": "vague", "label": "short prompts", "polarity": "holding-you-back",
     "detect": {"signal": "median_words", "op": "<", "value": 4},
     "coaching": "add context"},
    {"key": "plans", "label": "plans ahead", "polarity": "strength",
     "detect": {"signal": "plan_mode_used", "op": "==", "value": True},
     "coaching": "keep it up"},
]}


class HabitTests(unittest.TestCase):
    def test_numeric_rule_fires_with_evidence(self):
        sessions = [{"session_signals": {"median_words": 2.0}},
                    {"session_signals": {"median_words": 3.0}}]
        out = habits.detect(sessions, CATALOG)
        keys = {h["key"]: h for h in out["habits"]}
        self.assertIn("vague", keys)
        self.assertIn("2 of 2", keys["vague"]["evidence"])

    def test_bool_rule_requires_majority(self):
        sessions = [{"session_signals": {"plan_mode_used": True}},
                    {"session_signals": {"plan_mode_used": False}},
                    {"session_signals": {"plan_mode_used": True}}]
        out = habits.detect(sessions, CATALOG)
        self.assertIn("plans", {h["key"] for h in out["habits"]})

    def test_no_fire_when_below_threshold(self):
        sessions = [{"session_signals": {"median_words": 10.0}}]
        out = habits.detect(sessions, CATALOG)
        self.assertNotIn("vague", {h["key"] for h in out["habits"]})


if __name__ == "__main__":
    unittest.main()
