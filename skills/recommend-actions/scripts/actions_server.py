#!/usr/bin/env python3
"""Serve a ClaudeCoach profile dir over localhost so actions.html can persist Apply
selections back into actions.json.

recommend-actions/render.py embeds an apply-runtime in actions.html. When the page is
opened from this server (http://127.0.0.1:<port>/actions.html) instead of file://,
clicking Apply POSTs {"id","selected"} to /__actions__/select and this server flips that
action's apply.status in actions.json (selected <-> pending) atomically.

Health: GET /__actions__/health -> {"root": ..., "pid": ...}  (lets render.py reuse a
server already serving this profile dir).

Security: binds 127.0.0.1 only; the ONLY file ever written is <root>/actions.json; the
select POST requires an X-Actions-Select header (a CSRF guard browsers can't forge
cross-origin without a preflight this server never approves); body size-capped.
"""

import argparse
import functools
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 4577           # distinct from plan_server's 4477 so both can run at once
PORT_ATTEMPTS = 10
MAX_BYTES = 1 * 1024 * 1024
SELECT_PATH = "/__actions__/select"
HEALTH_PATH = "/__actions__/health"


def set_selected(doc, action_id, selected):
    """Flip one action's apply.status: selected<->pending. Return True if the id exists."""
    for a in doc.get("actions", []):
        if a.get("id") == action_id:
            a.setdefault("apply", {})["status"] = "selected" if selected else "pending"
            return True
    return False


class ActionsHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0] == HEALTH_PATH:
            payload = json.dumps(
                {"root": os.path.realpath(self.directory), "pid": os.getpid()}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def do_POST(self):
        if self.path.split("?", 1)[0] != SELECT_PATH:
            self.send_error(404, "Unknown endpoint")
            return
        # CSRF guard: a cross-origin page cannot send this custom header without a
        # preflight, which this server never approves.
        if self.headers.get("X-Actions-Select") != "1":
            self.send_error(403, "Missing X-Actions-Select header")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BYTES:
            self.send_error(400, "Missing or oversized request body")
            return
        try:
            req = json.loads(self.rfile.read(length))
            action_id = req["id"]
            selected = bool(req["selected"])
        except (ValueError, KeyError, TypeError):
            self.send_error(400, 'Body must be {"id": str, "selected": bool}')
            return
        # The ONLY file this server ever writes — never a path derived from the request.
        target = os.path.join(os.path.realpath(self.directory), "actions.json")
        if not os.path.isfile(target):
            self.send_error(404, "No actions.json in served root")
            return
        with open(target) as f:
            doc = json.load(f)
        if not set_selected(doc, action_id, selected):
            self.send_error(404, "Unknown action id")
            return
        # Single-user local UI flow: one writer at a time, so a fixed .tmp name is safe.
        tmp = target + ".tmp"
        with open(tmp, "w") as f:
            json.dump(doc, f, indent=2)
        os.replace(tmp, target)  # atomic: never leaves a half-written actions.json
        payload = json.dumps(
            {"id": action_id, "status": "selected" if selected else "pending"}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        sys.stderr.write("[actions-server] %s\n" % (fmt % args))


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--root", required=True,
                        help="profile dir to serve (holds actions.json + actions.html)")
    args = parser.parse_args()
    root = os.path.realpath(args.root)

    handler = functools.partial(ActionsHandler, directory=root)
    port = args.port
    httpd = None
    for _ in range(PORT_ATTEMPTS):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
            break
        except OSError:
            port += 1
    if httpd is None:
        sys.exit(f"actions-server: no free port in {args.port}..{port}")

    print(f"actions-server serving {root} at http://127.0.0.1:{port}/ (pid {os.getpid()})",
          flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
