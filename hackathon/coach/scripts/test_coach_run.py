import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coach_llm  # noqa: E402
import coach_run  # noqa: E402


def _session_jsonl(session_id, cwd):
    """A minimal but realistic Claude Code transcript that condenses above the
    MIN_CHUNK_TOKENS threshold (so it gets narrated + scored)."""
    long_user = ("Please refactor the authentication module so it is cleaner. "
                 "I want clear separation between the token parsing and the "
                 "permission checks, and please add tests that cover the "
                 "expired-token and missing-token edge cases before you change "
                 "any of the implementation code. Walk me through the plan first."
                 ) * 3
    entries = [
        {"type": "user", "cwd": cwd, "timestamp": "2026-06-01T10:00:00Z",
         "message": {"role": "user", "content": long_user}},
        {"type": "assistant", "timestamp": "2026-06-01T10:01:00Z",
         "message": {"role": "assistant", "content": [
             {"type": "text", "text": "Here is the plan. We could do option A "
              "or option B. I'll start by writing tests."},
             {"type": "tool_use", "name": "Write", "input": {
                 "file_path": "tests/test_auth.py", "content": "x" * 400}},
             {"type": "tool_use", "name": "Bash", "input": {
                 "command": "python3 -m pytest tests/test_auth.py"}},
         ]}},
        {"type": "user", "timestamp": "2026-06-01T10:02:00Z",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "content": "2 passed"}]}},
        {"type": "user", "cwd": cwd, "timestamp": "2026-06-01T10:03:00Z",
         "message": {"role": "user", "content":
                     "Looks good, now please implement the change and verify it "
                     "actually works end to end before committing anything."}},
        {"type": "assistant", "timestamp": "2026-06-01T10:04:00Z",
         "message": {"role": "assistant", "content": [
             {"type": "tool_use", "name": "Edit", "input": {
                 "file_path": "auth.py", "old_string": "a" * 50,
                 "new_string": "b" * 60}},
         ]}},
    ]
    return "\n".join(json.dumps(e) for e in entries) + "\n"


class FakeLlm:
    """Counts model calls; returns canned narrative/score outputs."""

    def __init__(self):
        self.text_calls = 0
        self.json_calls = 0

    def call_text(self, system_prompt, user_text, model="m", runner=None):
        self.text_calls += 1
        return ("**What they set out to do** A clean refactor.\n"
                "**What landed** Tests then implementation.\n"
                "<session_intent>shipping</session_intent>")

    def call_json(self, system_prompt, user_text, model="m", runner=None):
        self.json_calls += 1
        return {
            "title": "Refactored auth with tests first",
            "what_happened": "Wrote tests, then implemented.",
            "what_it_shows": "Plans and verifies.",
            "caveat": "Small sample.",
            "confidence": 0.8,
            "scores": {"outcomes": 7.0, "steering": 6.5, "quality": 7.5,
                       "planning": 7.0, "leverage": 6.0},
        }


class CoachRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="coach_run_test_")
        self.projects = os.path.join(self.tmp, "projects")
        # A non-git cwd so the run takes the synth-gitdata (session_only) path
        # and never shells out to a real repo.
        self.cwd = os.path.join(self.tmp, "workdir")
        os.makedirs(self.cwd)
        proj = os.path.join(self.projects, "-Volumes-myproj")
        os.makedirs(proj)
        with open(os.path.join(proj, "sess-abc.jsonl"), "w") as f:
            f.write(_session_jsonl("sess-abc", self.cwd))

        self.out_dir = os.path.join(self.tmp, "coach_out")
        self.work_dir = os.path.join(self.tmp, "work")

        self.fake = FakeLlm()
        self._orig_text = coach_llm.call_text
        self._orig_json = coach_llm.call_json
        coach_llm.call_text = self.fake.call_text
        coach_llm.call_json = self.fake.call_json

    def tearDown(self):
        coach_llm.call_text = self._orig_text
        coach_llm.call_json = self._orig_json
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self):
        return coach_run.run_once(
            self.projects, None, self.out_dir, "claude-haiku-4-5",
            self.work_dir, runner=None, updated_at="2026-06-13T00:00:00")

    def test_first_run_produces_valid_profile(self):
        prof, profile_path, stats = self._run()
        self.assertTrue(os.path.exists(profile_path))
        loaded = json.load(open(profile_path))
        # schema keys
        for key in ("updated_at", "overall", "band", "axes", "trend",
                    "n_sessions", "n_episodes", "disclaimer"):
            self.assertIn(key, loaded)
        self.assertEqual(loaded["n_sessions"], 1)
        self.assertEqual(loaded["n_episodes"], 1)
        self.assertIsNotNone(loaded["overall"])
        self.assertEqual(set(loaded["axes"]),
                         {"outcomes", "steering", "quality", "planning", "leverage"})
        # at least one model call happened on the first pass
        self.assertGreaterEqual(stats["narrative_calls"], 1)
        self.assertGreaterEqual(stats["score_calls"], 1)
        # episodes.json pool persisted
        self.assertTrue(os.path.exists(os.path.join(self.out_dir, "episodes.json")))
        # history appended
        self.assertTrue(os.path.exists(os.path.join(self.out_dir, "history.jsonl")))

    def test_second_run_makes_zero_model_calls(self):
        self._run()
        # reset counters; rerun with identical inputs
        self.fake.text_calls = 0
        self.fake.json_calls = 0
        _, _, stats = self._run()
        self.assertEqual(stats["narrative_calls"], 0,
                         "narratives should be served from cache on the 2nd pass")
        self.assertEqual(stats["score_calls"], 0,
                         "scores should be served from cache on the 2nd pass")
        self.assertEqual(self.fake.text_calls, 0)
        self.assertEqual(self.fake.json_calls, 0)

    def test_second_run_profile_matches_schema(self):
        self._run()
        prof, profile_path, _ = self._run()
        loaded = json.load(open(profile_path))
        expected = {"updated_at", "overall", "band", "axes", "strongest_axis",
                    "weakest_axis", "trend", "n_sessions", "n_episodes",
                    "disclaimer"}
        self.assertEqual(set(loaded), expected)

    def test_bad_project_dir_does_not_crash_run(self):
        # A dir whose jsonl is pure garbage — condense yields nothing usable.
        bad = os.path.join(self.projects, "-bad")
        os.makedirs(bad)
        with open(os.path.join(bad, "broken.jsonl"), "w") as f:
            f.write("{ not json\n!!!\n")
        prof, profile_path, _ = self._run()
        # The good project still produced a profile.
        self.assertTrue(os.path.exists(profile_path))
        self.assertEqual(json.load(open(profile_path))["n_sessions"], 1)


if __name__ == "__main__":
    unittest.main()
