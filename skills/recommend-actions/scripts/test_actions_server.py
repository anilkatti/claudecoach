import functools
import http.client
import json
import os
import sys
import threading
from http.server import ThreadingHTTPServer

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import actions_server as acts

DOC = {"schema_version": 1, "actions": [
    {"id": "a1", "apply": {"kind": "edit_file", "status": "pending"}},
    {"id": "a2", "apply": {"kind": "advisory", "status": "pending"}}]}


def test_set_selected_flips():
    doc = json.loads(json.dumps(DOC))
    assert acts.set_selected(doc, "a1", True) is True
    assert doc["actions"][0]["apply"]["status"] == "selected"
    assert acts.set_selected(doc, "a1", False) is True
    assert doc["actions"][0]["apply"]["status"] == "pending"


def test_set_selected_unknown_returns_false():
    assert acts.set_selected({"actions": []}, "zzz", True) is False


@pytest.fixture
def server(tmp_path):
    (tmp_path / "actions.json").write_text(json.dumps(DOC))
    handler = functools.partial(acts.ActionsHandler, directory=str(tmp_path))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)   # port 0 -> ephemeral
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield port, tmp_path
    httpd.shutdown()


def _post(port, path, body, headers):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    conn.request("POST", path, body=json.dumps(body), headers=headers)
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, data


_HDR = {"Content-Type": "application/json", "X-Actions-Select": "1"}


def test_health_returns_root(server):
    port, root = server
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    conn.request("GET", "/__actions__/health")
    r = conn.getresponse()
    info = json.loads(r.read())
    conn.close()
    assert r.status == 200
    assert os.path.realpath(info["root"]) == os.path.realpath(str(root))


def test_select_flips_status_on_disk(server):
    port, root = server
    status, data = _post(port, "/__actions__/select", {"id": "a1", "selected": True}, _HDR)
    assert status == 200
    assert json.loads(data)["status"] == "selected"
    doc = json.loads((root / "actions.json").read_text())
    assert doc["actions"][0]["apply"]["status"] == "selected"


def test_select_requires_header(server):
    port, root = server
    status, _ = _post(port, "/__actions__/select", {"id": "a1", "selected": True},
                      {"Content-Type": "application/json"})
    assert status == 403
    doc = json.loads((root / "actions.json").read_text())
    assert doc["actions"][0]["apply"]["status"] == "pending"   # untouched


def test_select_unknown_id_404(server):
    port, _ = server
    status, _ = _post(port, "/__actions__/select", {"id": "nope", "selected": True}, _HDR)
    assert status == 404


def test_unknown_post_path_404(server):
    port, _ = server
    status, _ = _post(port, "/__elsewhere__", {"x": 1}, _HDR)
    assert status == 404


def test_oversized_body_rejected(server):
    port, root = server
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    # Announce an oversized Content-Length; the server rejects on the header alone,
    # before reading any body, so we never need to transmit the large payload.
    conn.putrequest("POST", "/__actions__/select")
    conn.putheader("Content-Type", "application/json")
    conn.putheader("X-Actions-Select", "1")
    conn.putheader("Content-Length", str(acts.MAX_BYTES + 1))
    conn.endheaders()  # sends headers only
    r = conn.getresponse()
    r.read()
    conn.close()
    assert r.status == 400
    # disk untouched
    doc = json.loads((root / "actions.json").read_text())
    assert doc["actions"][0]["apply"]["status"] == "pending"


def test_select_missing_actions_json_404(tmp_path):
    handler = functools.partial(acts.ActionsHandler, directory=str(tmp_path))  # no actions.json written
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        status, _ = _post(port, "/__actions__/select", {"id": "a1", "selected": True}, _HDR)
        assert status == 404
    finally:
        httpd.shutdown()
