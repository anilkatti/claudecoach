import os

PROMPTS = os.path.join(os.path.dirname(__file__), "..", "prompts")
SPECIALISTS = ["capability_scout", "config_doctor", "pattern_smith", "practice_coach"]


def _read(name):
    with open(os.path.join(PROMPTS, name + ".md")) as f:
        return f.read()


def test_specialist_prompts_have_lane_placeholder_and_json_output():
    for name in SPECIALISTS:
        text = _read(name)
        assert "{{LANE_JSON}}" in text, name
        assert "ONLY this JSON" in text or "ONLY a JSON" in text, name
        assert "untrusted" in text.lower(), name           # injection guard
        assert "evidence" in text                          # evidence rail present


def test_research_prompts_reference_index_and_forbid_invention():
    for name in ["capability_scout", "practice_coach"]:
        text = _read(name)
        assert "{{INDEX_JSON}}" in text, name
        assert "never" in text.lower() and any(
            w in text.lower() for w in ("invent", "point to", "cite")), name


def test_synthesizer_prompt_has_candidates_and_actions_schema():
    text = _read("action_synthesizer")
    assert "{{CANDIDATES_JSON}}" in text
    assert "{{PROFILE_JSON}}" in text
    assert "not_recommended" in text
    assert "do_now" in text and "consider" in text and "fyi" in text
