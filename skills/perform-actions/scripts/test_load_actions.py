import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import load_actions as la

DOC = {"schema_version": 1,
       "actions": [{"id": "a1", "apply": {"kind": "advisory", "status": "pending"}}]}


def _write(tmp_path, cwd="/Volumes/x"):
    d = tmp_path / "profiles" / la.encode_cwd(cwd)
    d.mkdir(parents=True)
    (d / "actions.json").write_text(json.dumps(DOC))
    return cwd


def test_encode_cwd_matches_profile_rule():
    assert la.encode_cwd("/Volumes/Sources/cc") == "-Volumes-Sources-cc"


def test_load_actions_missing(tmp_path):
    res = la.load_actions("/no/such/cwd", profiles_root=str(tmp_path / "profiles"))
    assert res["error"] == "no_actions"


def test_load_actions_ok(tmp_path):
    cwd = _write(tmp_path)
    res = la.load_actions(cwd, profiles_root=str(tmp_path / "profiles"))
    assert "error" not in res
    assert res["doc"]["actions"][0]["id"] == "a1"
    assert res["path"].endswith("actions.json")


def test_load_actions_bad_json(tmp_path):
    cwd = "/Volumes/x"
    d = tmp_path / "profiles" / la.encode_cwd(cwd)
    d.mkdir(parents=True)
    (d / "actions.json").write_text("not json{")
    res = la.load_actions(cwd, profiles_root=str(tmp_path / "profiles"))
    assert res["error"] == "bad_json"


def test_cli_emits_json(tmp_path):
    cwd = _write(tmp_path)
    out = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "load_actions.py"),
         cwd, "--profiles-root", str(tmp_path / "profiles")],
        capture_output=True, text=True, check=True).stdout
    doc = json.loads(out)
    assert doc["n_actions"] == 1 and doc["path"].endswith("actions.json")


def test_cli_missing_emits_error(tmp_path):
    out = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "load_actions.py"),
         "/no/such", "--profiles-root", str(tmp_path / "profiles")],
        capture_output=True, text=True).stdout
    assert json.loads(out)["error"] == "no_actions"
