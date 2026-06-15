import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import profile as profile_mod  # noqa: E402


def _agg(axes, overall, band=None, n=3):
    return {"episodes_scored": n, "axes": axes, "overall_score": overall,
            "band": band}


class ProfileTests(unittest.TestCase):
    def test_basic_assembly(self):
        agg = _agg({"outcomes": 7.0, "steering": 6.0, "quality": 8.0,
                    "planning": 5.0, "leverage": 6.5}, 6.5, band="Solid", n=4)
        trend = {"deltas": {"overall": 1.2}, "note": None}
        p = profile_mod.build_profile(agg, trend, None, None, 10, "2026-06-13T00:00:00")
        self.assertEqual(p["updated_at"], "2026-06-13T00:00:00")
        self.assertEqual(p["overall"], 6.5)
        self.assertEqual(p["band"], "Solid")
        self.assertEqual(p["n_sessions"], 10)
        self.assertEqual(p["n_episodes"], 4)
        self.assertEqual(set(p["axes"]), {"outcomes", "steering", "quality",
                                          "planning", "leverage"})
        self.assertEqual(p["disclaimer"],
                         "Haiku-scored & nondeterministic; a snapshot, not a verdict.")

    def test_band_derived_when_absent(self):
        agg = _agg({"outcomes": 8.5}, 8.5)  # no band in aggregate
        p = profile_mod.build_profile(agg, {}, None, None, 1, "t")
        self.assertEqual(p["band"], "Strong")  # 8 <= 8.5 < 9

    def test_strongest_and_weakest(self):
        agg = _agg({"outcomes": 7.0, "steering": 9.0, "quality": 4.0}, 6.7)
        p = profile_mod.build_profile(agg, {}, None, None, 1, "t")
        self.assertEqual(p["strongest_axis"], {"key": "steering",
                                               "name": "Steering the AI", "score": 9.0})
        self.assertEqual(p["weakest_axis"], {"key": "quality",
                                             "name": "Quality bar", "score": 4.0})

    def test_trend_delta_and_note_passthrough(self):
        agg = _agg({"outcomes": 7.0}, 7.0)
        trend = {"deltas": {"outcomes": -0.5, "overall": -0.5},
                 "note": "still early"}
        p = profile_mod.build_profile(agg, trend, None, None, 1, "t")
        self.assertEqual(p["trend"]["overall_delta"], -0.5)
        self.assertEqual(p["trend"]["note"], "still early")

    def test_trend_null_delta_when_absent(self):
        agg = _agg({"outcomes": 7.0}, 7.0)
        trend = {"deltas": None, "note": "not enough time span to show a trend yet"}
        p = profile_mod.build_profile(agg, trend, None, None, 1, "t")
        self.assertIsNone(p["trend"]["overall_delta"])
        self.assertEqual(p["trend"]["note"],
                         "not enough time span to show a trend yet")

    def test_no_axes_graceful(self):
        agg = {"episodes_scored": 0, "axes": {}, "overall_score": None,
               "band": None}
        p = profile_mod.build_profile(agg, {}, None, None, 0, "t")
        self.assertEqual(p["axes"], {})
        self.assertIsNone(p["overall"])
        self.assertIsNone(p["band"])
        self.assertNotIn("strongest_axis", p)
        self.assertNotIn("weakest_axis", p)

    def test_byte_determinism(self):
        agg = _agg({"outcomes": 7.0, "steering": 6.0, "quality": 8.0,
                    "planning": 5.0, "leverage": 6.5}, 6.5, band="Solid")
        trend = {"deltas": {"overall": 0.3}, "note": None}
        p1 = profile_mod.build_profile(agg, trend, None, None, 5, "t")
        p2 = profile_mod.build_profile(agg, trend, None, None, 5, "t")
        self.assertEqual(json.dumps(p1, sort_keys=True),
                         json.dumps(p2, sort_keys=True))

    def test_schema_keys_exact(self):
        agg = _agg({"outcomes": 7.0}, 7.0, band="Solid")
        p = profile_mod.build_profile(agg, {"deltas": {}, "note": None},
                                      None, None, 1, "t")
        expected = {"updated_at", "overall", "band", "axes", "strongest_axis",
                    "weakest_axis", "trend", "n_sessions", "n_episodes",
                    "disclaimer"}
        self.assertEqual(set(p), expected)
        self.assertEqual(set(p["trend"]), {"overall_delta", "note"})


if __name__ == "__main__":
    unittest.main()
