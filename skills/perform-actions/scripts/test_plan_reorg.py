import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import plan_reorg as pr

DOC = {"actions": [
    {"id": "e1", "apply": {"kind": "edit_file", "target_path": "/p/CLAUDE.md"}},
    {"id": "e2", "apply": {"kind": "edit_file", "target_path": "/p/CLAUDE.md"}},
    {"id": "e3", "apply": {"kind": "edit_file", "target_path": "/p/memory/MEMORY.md"}},
    {"id": "ar", "apply": {"kind": "archive", "target_path": None}},
    {"id": "e4", "apply": {"kind": "edit_file"}},  # edit_file with no target_path
]}


def test_groups_edit_file_by_target_path():
    groups = pr.group_edits(DOC, ["e1", "e2", "e3"])
    by = {g["target_path"]: g["action_ids"] for g in groups}
    assert by["/p/CLAUDE.md"] == ["e1", "e2"]
    assert by["/p/memory/MEMORY.md"] == ["e3"]


def test_ignores_unapproved_and_non_edit_file():
    groups = pr.group_edits(DOC, ["e1", "ar"])  # ar is archive; e2/e3 not approved
    assert groups == [{"target_path": "/p/CLAUDE.md", "action_ids": ["e1"]}]


def test_skips_edit_file_without_target_path():
    assert pr.group_edits(DOC, ["e4"]) == []


def test_cli(tmp_path):
    p = tmp_path / "actions.json"
    p.write_text(json.dumps(DOC))
    out = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "plan_reorg.py"),
         str(p), "e1", "e2"], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [{"target_path": "/p/CLAUDE.md", "action_ids": ["e1", "e2"]}]
