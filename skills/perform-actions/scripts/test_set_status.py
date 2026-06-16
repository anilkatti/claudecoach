import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import set_status as ss


def _doc():
    return {"actions": [{"id": "a1", "apply": {"kind": "advisory", "status": "pending"}},
                        {"id": "a2", "apply": {"kind": "archive", "status": "pending"}}]}


def test_set_status_updates_target():
    doc = _doc()
    assert ss.set_status(doc, "a2", "applied") is True
    assert doc["actions"][1]["apply"]["status"] == "applied"
    assert doc["actions"][0]["apply"]["status"] == "pending"  # others untouched


def test_set_status_unknown_id():
    assert ss.set_status(_doc(), "nope", "applied") is False


def test_update_file_persists(tmp_path):
    p = tmp_path / "actions.json"
    p.write_text(json.dumps(_doc()))
    assert ss.update_file(str(p), "a1", "skipped") is True
    assert json.loads(p.read_text())["actions"][0]["apply"]["status"] == "skipped"


def test_cli(tmp_path):
    p = tmp_path / "actions.json"
    p.write_text(json.dumps(_doc()))
    out = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "set_status.py"),
         str(p), "a2", "applied"], capture_output=True, text=True, check=True).stdout
    assert json.loads(out)["updated"] is True
    assert json.loads(p.read_text())["actions"][1]["apply"]["status"] == "applied"
