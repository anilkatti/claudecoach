import json
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import load_actions as la
import plan_reorg as pr
import set_status as ss
import apply


def test_load_group_apply_status_round_trip(tmp_path):
    # 1. load_actions finds the written actions.json for this cwd
    cwd = "/Volumes/proj"
    d = tmp_path / "profiles" / la.encode_cwd(cwd)
    d.mkdir(parents=True)
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# project\n")
    actions = {"schema_version": 1, "actions": [
        {"id": "cap", "priority": "do_now", "title": "Capture test cmd", "rationale": "r",
         "apply": {"kind": "edit_file", "target_path": str(claude_md),
                   "preview": "+ Test: pytest -q", "reversible": True, "status": "pending"}}]}
    apath = d / "actions.json"
    apath.write_text(json.dumps(actions))
    loaded = la.load_actions(cwd, profiles_root=str(tmp_path / "profiles"))
    assert loaded["doc"]["actions"][0]["id"] == "cap"

    # 2. plan_reorg groups the approved edit_file action by its target file
    groups = pr.group_edits(loaded["doc"], ["cap"])
    assert groups == [{"target_path": str(claude_md), "action_ids": ["cap"]}]

    # 3. apply.apply_edit writes the (reorganized) content reversibly
    res = apply.apply_edit(str(claude_md), "# project\nTest: pytest -q\n")
    assert "pytest -q" in claude_md.read_text()
    assert open(res["backed_up_to"]).read() == "# project\n"

    # 4. set_status marks the action applied back in actions.json
    assert ss.update_file(str(apath), "cap", "applied") is True
    assert json.loads(apath.read_text())["actions"][0]["apply"]["status"] == "applied"
