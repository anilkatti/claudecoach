import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import habits  # noqa: E402

# Signal names produced inside session_signals by scripts/events.py. A catalog
# rule whose signal is absent here silently never fires, so this set is a
# tripwire: keep it in sync with events.py if you add a signal a habit needs.
REAL_SESSION_SIGNALS = frozenset({
    "user_message_count", "total_user_words", "avg_prompt_length_words",
    "tool_count", "assistant_count", "duration_minutes", "messages_per_minute",
    "tools_per_message", "git_commit_count", "unique_tools", "plan_mode_used",
    "task_tool_used", "worktree_used", "files_modified_count", "test_run_count",
    "error_count", "test_pass_rate", "tdd_discipline_ratio", "recovery_speed",
    "error_retry_ratio", "imperative_prompts", "confirmation_requests",
    "kill_decisions", "review_checks", "self_corrections", "critiques",
    "domain_corrections", "hypothesis_driven", "debugging_messages",
    "architecture_discussions", "narrative_framing", "product_references",
    "substantive_messages", "terse_messages", "substantive_ratio",
    "courtesy_messages", "skills_invoked",
})

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


class ShippedCatalogTests(unittest.TestCase):
    def test_every_catalog_signal_is_a_real_session_signal(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "reference", "habit_catalog.json")
        catalog = json.load(open(path))
        for h in catalog["habits"]:
            sig = h["detect"]["signal"]
            self.assertIn(sig, REAL_SESSION_SIGNALS,
                          "habit %r points at signal %r not produced by events.py "
                          "(rule would silently never fire)" % (h["key"], sig))


if __name__ == "__main__":
    unittest.main()
