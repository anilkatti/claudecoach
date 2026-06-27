import os

PROMPTS = os.path.join(os.path.dirname(__file__), "..", "prompts")
SPECIALISTS = ["capability_scout", "config_doctor", "pattern_smith", "practice_coach"]


def _read(name):
    with open(os.path.join(PROMPTS, name + ".md")) as f:
        return f.read()


REFERENCE = os.path.join(os.path.dirname(__file__), "..", "reference")


def _read_ref(name):
    with open(os.path.join(REFERENCE, name)) as f:
        return f.read()


def test_sources_reference_lists_sources_and_levers():
    text = _read_ref("sources.md")
    low = text.lower()
    # adoption sources (incl. the two real-usage proxies) + the registry
    assert "registry.modelcontextprotocol.io" in text
    assert "pulsemcp" in low and "glama" in low
    assert "anthropics/claude-plugins-official" in text
    # the verified hygiene levers, by exact key
    assert "disable-model-invocation" in text
    assert "skillOverrides" in text and "settings.local.json" in text
    assert "paths:" in text
    # verified guidance + the standing caveats
    assert "200 lines" in low                       # CLAUDE.md size discipline
    assert "deferred by default" in low             # MCP is not a context hog
    assert "visibility, not adoption" in low        # triangulation caveat
    assert "re-verify" in low                       # keys drift
    assert "plugin skills are exempt" in low        # skillOverrides exemption


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


def test_capability_scout_cli_first_recalibrated():
    text = _read("capability_scout")
    low = text.lower()
    assert "cli" in low and "genuinely can't" in low          # CLI-first kept
    assert "simplicity" in low                                 # justified by simplicity, not token cost
    assert "deferred by default" in low or "minimal impact" in low   # MCP is deferred-cheap
    # the obsolete token-cost rationale for refusing an MCP is gone
    assert "always-on tool-schema token cost" not in low
    # don't suppress structurally-leverageful MCP
    assert "structured/programmatic access" in low


def test_capability_scout_surveys_adoption_sources():
    text = _read("capability_scout")
    low = text.lower()
    assert "reference/sources.md" in text                      # cites the methodology reference
    assert "adoption signal" in low                            # must cite a real signal
    assert "pulsemcp" in low or "glama" in low                 # a real-usage proxy named
    assert "visibility, not adoption" in low                   # triangulation caveat


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


def test_config_doctor_profile_management_lens():
    text = _read("config_doctor")
    low = text.lower()
    assert "skill_usage" in text                        # ranks the prunable subset by usage
    assert "reference/sources.md" in text               # levers come from the reference
    # team vs personal: repo not the user's to delete; suppress-for-self lever + location
    assert "team-shared" in low
    assert "settings.local.json" in low
    # always-on bloat targeting + verified size guidance
    assert "always_on.sources" in text
    assert "200 lines" in low
    # MCP de-emphasized (deferred-cheap)
    assert "minimal context impact" in low or "deferred by default" in low
    # honesty rail preserved
    assert "sampled sessions" in low


def test_synthesizer_balances_families_in_priority():
    text = _read("action_synthesizer")
    low = text.lower()
    assert "crowd out" in low
    assert "acquire" in low
    # high always-on bloat trims and strong adoption finds are do_now/consider eligible
    assert "bloat" in low
    assert "adoption" in low
