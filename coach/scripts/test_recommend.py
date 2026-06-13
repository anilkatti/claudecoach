import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recommend  # noqa: E402


class RecommendTests(unittest.TestCase):
    def test_prep_excludes_already_used_and_lists_weak_axes(self):
        payload = recommend.prep(
            per_axis={"outcomes": 5.0, "steering": 7.5, "quality": 6.0,
                      "planning": 4.5, "leverage": 8.0},
            habits={"habits": [{"key": "vague", "label": "short prompts",
                                "polarity": "holding-you-back",
                                "coaching": "add context"}]},
            skills_used=["brainstorming"],
            index={"skills": [
                {"name": "brainstorming", "one_liner": "x", "tags": ["planning"]},
                {"name": "writing-plans", "one_liner": "y", "tags": ["planning"]}]},
        )
        names = [s["name"] for s in payload["catalog"]]
        self.assertIn("writing-plans", names)
        self.assertNotIn("brainstorming", names)  # already used -> excluded
        self.assertEqual(payload["weak_axes"][0]["axis"], "planning")  # lowest first

    def test_finalize_caps_and_passes_through(self):
        raw = {"recommend": [{"name": "a", "why": "w", "helps_axis": "x"}] * 7,
               "reconsider": []}
        out = recommend.finalize(raw)
        self.assertEqual(len(out["recommend"]), 5)
        self.assertEqual(out["reconsider"], [])


if __name__ == "__main__":
    unittest.main()
