import os

PROMPTS = os.path.join(os.path.dirname(__file__), "..", "prompts")
ACTION_DOERS = ["installer", "archiver", "scaffolder", "handoff"]


def _read(name):
    with open(os.path.join(PROMPTS, name + ".md")) as f:
        return f.read()


def test_all_doers_have_untrusted_guard():
    for name in ACTION_DOERS + ["context_reorganizer"]:
        assert "untrusted" in _read(name).lower(), name


def test_action_doers_take_action_json():
    for name in ACTION_DOERS:
        assert "{{ACTION_JSON}}" in _read(name), name


def test_installer_verifies_and_archiver_is_reversible():
    assert "verify" in _read("installer").lower()
    archiver = _read("archiver").lower()
    assert "restore" in archiver and ("archive" in archiver)


def test_reorganizer_has_placeholders_and_rails():
    text = _read("context_reorganizer")
    for ph in ("{{TARGET_PATH}}", "{{CURRENT_CONTENT}}", "{{ACTIONS}}"):
        assert ph in text, ph
    low = text.lower()
    assert "preserve" in low                 # don't rewrite untouched content
    assert "only" in low and "approved" in low  # only approved actions' intent
    assert "conflict" in low                 # surface conflicts, don't guess
    assert "entire" in low or "full" in low  # output the whole file
