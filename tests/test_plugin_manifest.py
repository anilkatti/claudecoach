"""Offline: the packaged plugin/marketplace manifests are valid.

`claude plugin validate --strict` fails on unknown fields, missing metadata, and
anything the runtime would only tolerate — so this is the cheap first gate before
the live install tests. No network, no model.
"""
import helpers


def test_manifest_validates_strict(plugin_cli):
    result = plugin_cli("validate", str(helpers.REPO_ROOT), "--strict")
    assert "validation passed" in result.stdout.lower(), result.stdout


def test_marketplace_declares_the_plugin():
    names = {p["name"] for p in helpers.MARKETPLACE_MANIFEST["plugins"]}
    assert helpers.PLUGIN_NAME in names, (
        f"plugin.json name {helpers.PLUGIN_NAME!r} not declared in marketplace.json "
        f"plugins {names}")


def test_repo_ships_three_known_skills():
    # The flow under test bundles exactly the three ClaudeCoach skills.
    assert helpers.expected_skill_names() == {
        "profile-builder", "recommend-actions", "perform-actions",
    }
