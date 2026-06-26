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


def test_practice_coach_references_index_and_forbids_invention():
    text = _read("practice_coach")
    assert "{{INDEX_JSON}}" in text
    assert "never" in text.lower() and any(
        w in text.lower() for w in ("invent", "point to", "cite"))


def test_capability_scout_is_live_scoped_no_static_index():
    text = _read("capability_scout")
    assert "{{INDEX_JSON}}" not in text           # no static catalog anymore
    assert "{{LANE_JSON}}" in text
    assert "work_type" in text                     # research is scoped to the profile
    assert "verify" in text.lower()                # URL-verification rail
    assert "never" in text.lower() and "invent" in text.lower()


def test_synthesizer_prompt_has_candidates_and_actions_schema():
    text = _read("action_synthesizer")
    assert "{{CANDIDATES_JSON}}" in text
    assert "{{PROFILE_JSON}}" in text
    assert "not_recommended" in text
    assert "do_now" in text and "consider" in text and "fyi" in text


def test_capability_scout_surfaces_wellknown_options():
    text = _read("capability_scout")
    assert "well-known" in text.lower()
    assert "verify" in text.lower()                      # URL rail still present
    assert "never" in text.lower() and "invent" in text.lower()


def test_capability_scout_is_cli_first():
    low = _read("capability_scout").lower()
    assert "cli" in low
    assert "earn its place" in low and "genuinely can't" in low
    assert "token cost" in low
    # the old blanket "prefer MCP" line is removed
    assert "prefer mcp for a live-data/tool gap, a skill for a procedure" not in low


def test_config_doctor_has_skill_reorg_lens():
    text = _read("config_doctor")
    assert "reorganize" in text.lower()
    assert "owned_capabilities" in text
    assert "archive" in text.lower()


def test_config_doctor_skill_hygiene_levers():
    text = _read("config_doctor")
    low = text.lower()
    # right-lever-per-case, not always "archive"
    assert "disable-model-invocation" in low
    assert "skilloverrides" in low
    # framed as triggering/selection clarity, not inflated token savings
    assert "triggering" in low
    assert "~100 tokens" in text or "100 tokens" in text
    # standalone-only caveat so it never tells a plugin skill to use these levers
    assert "standalone" in low and "plugin" in low
    # rail preserved
    assert "sampled sessions" in low


def test_config_doctor_respects_global_personal_scope():
    low = _read("config_doctor").lower()
    # personal-scope capabilities are global; don't archive the personal copy of a cross-scope dup
    assert "deliberately global" in low
    assert "keep them in sync" in low
    assert "within the same scope" in low      # archive reserved for same-scope dups / dead weight


def test_synthesizer_balances_families_in_priority():
    text = _read("action_synthesizer")
    assert "crowd out" in text.lower()
    assert "acquire" in text.lower()
