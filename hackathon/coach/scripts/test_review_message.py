#!/usr/bin/env python3
"""Tests for review_message — normalization + the review() path with a fake runner."""
import json
import unittest

import review_message
from review_message import normalize, review

# A minimal system prompt so review() doesn't read the real file under test.
PROMPT = "review one message"


def runner_returning(text):
    """A coach_llm-style runner(argv, stdin) -> str that ignores input."""
    return lambda argv, stdin: text


class NormalizeTests(unittest.TestCase):
    def test_keeps_nudge_focus_and_known_scores(self):
        out = normalize({
            "nudge": "  Right-sized ask — nice and clear.  ",
            "focus_axis": "steering",
            "scores": {"steering": 7, "bogus": 9},
        })
        self.assertEqual(out["nudge"], "Right-sized ask — nice and clear.")
        self.assertEqual(out["focus_axis"], "steering")
        self.assertEqual(out["scores"], {"steering": 7.0})

    def test_drops_unknown_focus_axis(self):
        out = normalize({"nudge": "Good.", "focus_axis": "vibes"})
        self.assertNotIn("focus_axis", out)

    def test_drops_bool_and_nonnumeric_scores(self):
        out = normalize({"nudge": "Good.",
                         "scores": {"steering": True, "quality": "high"}})
        self.assertNotIn("scores", out)  # nothing valid -> key omitted

    def test_missing_nudge_raises(self):
        with self.assertRaises(ValueError):
            normalize({"focus_axis": "steering"})

    def test_empty_nudge_raises(self):
        with self.assertRaises(ValueError):
            normalize({"nudge": "   "})

    def test_non_dict_raises(self):
        with self.assertRaises(ValueError):
            normalize(["not", "a", "dict"])


class ReviewTests(unittest.TestCase):
    def test_review_extracts_from_clean_json(self):
        text = json.dumps({"nudge": "Try one clear instruction.",
                           "focus_axis": "steering"})
        out = review("fix the bug", runner=runner_returning(text), prompt=PROMPT)
        self.assertEqual(out["nudge"], "Try one clear instruction.")
        self.assertEqual(out["focus_axis"], "steering")

    def test_review_tolerates_prose_and_fences(self):
        # coach_llm.extract_json digs the object out of surrounding text.
        text = "Here you go:\n```json\n{\"nudge\": \"Nice, crisp ask.\"}\n```\n"
        out = review("ship it", runner=runner_returning(text), prompt=PROMPT)
        self.assertEqual(out["nudge"], "Nice, crisp ask.")

    def test_review_raises_when_no_nudge(self):
        text = json.dumps({"focus_axis": "steering"})
        with self.assertRaises(Exception):
            review("hello", runner=runner_returning(text), prompt=PROMPT)


if __name__ == "__main__":
    unittest.main()
