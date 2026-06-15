import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coach_llm  # noqa: E402


class FakeRunner:
    """Returns successive canned outputs; records call count."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def __call__(self, argv, stdin):
        self.calls += 1
        if not self.outputs:
            return ""
        return self.outputs.pop(0)


class CoachLlmTests(unittest.TestCase):
    def test_call_json_parses_fenced_output(self):
        runner = FakeRunner(['```json\n{"scores": {"outcomes": 7.0}}\n```'])
        out = coach_llm.call_json("sys", "user", runner=runner)
        self.assertEqual(out, {"scores": {"outcomes": 7.0}})
        self.assertEqual(runner.calls, 1)

    def test_call_json_parses_prose_wrapped_output(self):
        runner = FakeRunner([
            'Here is the result you asked for:\n'
            '{"title": "did a thing", "confidence": 0.8}\n'
            'Hope that helps!'])
        out = coach_llm.call_json("sys", "user", runner=runner)
        self.assertEqual(out["title"], "did a thing")
        self.assertEqual(out["confidence"], 0.8)

    def test_call_json_retries_empty_then_valid(self):
        runner = FakeRunner(["", '{"ok": true}'])
        out = coach_llm.call_json("sys", "user", runner=runner)
        self.assertEqual(out, {"ok": True})
        self.assertEqual(runner.calls, 2)

    def test_call_json_retries_unparseable_then_valid(self):
        runner = FakeRunner(["not json at all", '{"ok": true}'])
        out = coach_llm.call_json("sys", "user", runner=runner)
        self.assertEqual(out, {"ok": True})
        self.assertEqual(runner.calls, 2)

    def test_call_json_raises_after_exhausting_retries(self):
        runner = FakeRunner(["nope", "still nope", "nope again", "extra"])
        with self.assertRaises(RuntimeError):
            coach_llm.call_json("sys", "user", runner=runner)
        # 1 initial + MAX_RETRIES extra attempts
        self.assertEqual(runner.calls, coach_llm.MAX_RETRIES + 1)

    def test_call_text_returns_stripped(self):
        runner = FakeRunner(["  pong  \n"])
        self.assertEqual(coach_llm.call_text("sys", "user", runner=runner), "pong")

    def test_call_text_retries_empty_then_valid(self):
        runner = FakeRunner(["", "   ", "answer"])
        self.assertEqual(coach_llm.call_text("sys", "user", runner=runner), "answer")
        self.assertEqual(runner.calls, 3)

    def test_call_text_raises_after_exhausting_retries(self):
        runner = FakeRunner(["", "", "", ""])
        with self.assertRaises(RuntimeError):
            coach_llm.call_text("sys", "user", runner=runner)
        self.assertEqual(runner.calls, coach_llm.MAX_RETRIES + 1)

    def test_extract_json_nested_object(self):
        text = 'prefix {"a": {"b": 1}, "c": [1, 2]} suffix'
        self.assertEqual(coach_llm.extract_json(text), {"a": {"b": 1}, "c": [1, 2]})

    def test_extract_json_none_when_absent(self):
        self.assertIsNone(coach_llm.extract_json("no braces here"))

    def test_default_argv_uses_verified_flags(self):
        argv = coach_llm._argv("MY SYS", "claude-haiku-4-5")
        self.assertEqual(argv, ["claude", "-p", "--model", "claude-haiku-4-5",
                                "--system-prompt", "MY SYS",
                                "--output-format", "text"])


if __name__ == "__main__":
    unittest.main()
