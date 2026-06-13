import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coach_aggregate as ca  # noqa: E402


class CoachAggregateTests(unittest.TestCase):
    def test_axes_are_the_five_plain_keys(self):
        self.assertEqual(ca.AXES,
                         ["outcomes", "steering", "quality", "planning", "leverage"])

    def test_band_labels_are_softened(self):
        self.assertEqual(ca.band_for_score(2.0), "Getting started")
        self.assertEqual(ca.band_for_score(5.0), "Finding your footing")
        self.assertEqual(ca.band_for_score(7.0), "Solid")
        self.assertEqual(ca.band_for_score(8.5), "Strong")
        self.assertEqual(ca.band_for_score(9.5), "Exceptional")

    def test_rollup_confidence_weighted_and_omits_unscored_axes(self):
        eps = [
            {"scores": {"outcomes": 8.0, "steering": 6.0}, "confidence": 1.0},
            {"scores": {"outcomes": 6.0}, "confidence": 0.5},
        ]
        per_axis, overall = ca.rollup(eps)
        self.assertAlmostEqual(per_axis["outcomes"], (8.0 + 6.0 * 0.5) / 1.5, places=2)
        self.assertEqual(per_axis["steering"], 6.0)
        self.assertNotIn("quality", per_axis)
        self.assertIsNotNone(overall)


if __name__ == "__main__":
    unittest.main()
