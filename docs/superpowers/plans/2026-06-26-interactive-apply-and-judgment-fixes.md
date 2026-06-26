# Interactive Apply in actions.html + two judgment fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `actions.html` interactive — a real **Apply → ✓ Selected for application** button per card that persists into `actions.json` via a localhost server, read back by `/perform-actions` — and fix two naive coach judgments (archiving global personal skills; pushing MCP over an existing CLI).

**Architecture:** Extend the existing `apply.status` field with one value, `selected`. A hardened `actions_server.py` (the commentable-plans `plan_server.py` pattern) serves the profile dir and flips that status on button click; `render.py` opens the report through it. `/perform-actions` filters to `status=="selected"`, still confirming each. Two prompt edits fix the judgment. `actions.json` stays the single source of truth — nothing parses HTML.

**Tech Stack:** Python 3 standard library only (`http.server`, `json`, `argparse`, `subprocess`, `webbrowser`); pytest; vanilla embedded JS/CSS. No new dependencies.

## Global Constraints

- **Python standard library only** — no new third-party deps in any script.
- **TDD, pytest, LLM-free** — failing test first; all tests run offline and fast (no model calls, no outbound network beyond `127.0.0.1`).
- **Scripts run from each skill's own base directory**; the user's project is passed as an arg.
- **Server hardening (copied from `plan_server.py`):** bind `127.0.0.1` only; the only file ever written is `<served-root>/actions.json`; the select POST requires header `X-Actions-Select: 1` (CSRF guard); request body size-capped; writes are atomic (`tmp` + `os.replace`).
- **`set_status.py` stays untouched** — it still writes only `applied|skipped|pending`; the server owns the `selected↔pending` flip.
- **Audience-neutral** copy; **reversible / opt-in** apply semantics preserved (per-action confirmation in `/perform-actions` is NOT removed).
- **Single source of truth is `actions.json`** — the new value is additive and backward-compatible.

---

### Task 1: config-doctor — personal scope is deliberately global

**Files:**
- Modify: `skills/recommend-actions/prompts/config_doctor.md` (the "reorganize / right-size your skills" lens, ~lines 21–46)
- Test: `skills/recommend-actions/scripts/test_prompts.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing code-level; a structural assertion that the new guidance is present.

- [ ] **Step 1: Write the failing test**

Add to `skills/recommend-actions/scripts/test_prompts.py`:

```python
def test_config_doctor_respects_global_personal_scope():
    low = _read("config_doctor").lower()
    # personal-scope capabilities are global; don't archive the personal copy of a cross-scope dup
    assert "deliberately global" in low
    assert "keep them in sync" in low
    assert "within the same scope" in low      # archive reserved for same-scope dups / dead weight
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py::test_config_doctor_respects_global_personal_scope -v`
Expected: FAIL (`assert "deliberately global" in low`).

- [ ] **Step 3: Edit the prompt**

In `prompts/config_doctor.md`, the lever list under "reorganize / right-size your skills" currently begins:

```
  Then pick the **lightest lever that fits the case** — not always
  "archive":
  - **true duplicate or dead weight** → `archive` the redundant copy (apply `archive`;
    a reversible move, never a delete).
```

Insert a guardrail paragraph immediately **before** the `Then pick the lightest lever` line, and tighten the first lever bullet, so the section reads:

```
  **Personal scope is deliberately global.** A capability in **personal** scope
  (`~/.claude/...`) is meant to apply across ALL the user's projects, including ones
  outside any given repo. A **personal↔repo** or **personal↔plugin** overlap is therefore
  *expected, not redundancy* — archiving the personal copy to dedupe a repo or plugin copy
  would strip it from every other project the user works in, so do **not** recommend that.
  At most emit a low-priority note ("duplicated across scopes — keep them in sync"). Reserve
  `archive` for genuine dead weight: a redundant copy **within the same scope**, or a
  capability the evidence shows is obsolete. When unsure about a cross-scope overlap, leave
  it alone.
  Then pick the **lightest lever that fits the case** — not always
  "archive":
  - **true duplicate within the same scope, or dead weight** → `archive` the redundant copy
    (apply `archive`; a reversible move, never a delete).
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py -v`
Expected: PASS (new test green; existing `test_config_doctor_*` still green).

- [ ] **Step 5: Commit**

```bash
git add skills/recommend-actions/prompts/config_doctor.md skills/recommend-actions/scripts/test_prompts.py
git commit -m "fix(config-doctor): treat personal scope as global; stop archiving personal duplicates"
```

---

### Task 2: capability-scout — CLI-first, MCP must earn its place

**Files:**
- Modify: `skills/recommend-actions/prompts/capability_scout.md:29`
- Test: `skills/recommend-actions/scripts/test_prompts.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a structural assertion that CLI-first guidance is present and the blanket "prefer MCP" line is gone.

- [ ] **Step 1: Write the failing test**

Add to `skills/recommend-actions/scripts/test_prompts.py`:

```python
def test_capability_scout_is_cli_first():
    low = _read("capability_scout").lower()
    assert "cli" in low
    assert "earn its place" in low and "genuinely can't" in low
    assert "token cost" in low
    # the old blanket "prefer MCP" line is removed
    assert "prefer mcp for a live-data/tool gap, a skill for a procedure" not in low
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py::test_capability_scout_is_cli_first -v`
Expected: FAIL (`assert "earn its place" in low`).

- [ ] **Step 3: Edit the prompt**

In `prompts/capability_scout.md`, replace the single line:

```
- Prefer MCP for a live-data/tool gap, a skill for a procedure, a plugin for a bundle.
```

with:

```
- **A CLI you already use is the default — make an MCP earn its place.** Before proposing
  an MCP, check `tools_and_materials` and `owned_capabilities` for an existing CLI that
  already covers the gap (e.g. `gh`, `docker`, `aws`). If one exists, recommend an MCP
  **only** when it gives something the CLI genuinely can't — structured/programmatic access
  the model can't reliably parse from CLI text, or a materially tighter loop — and say so
  explicitly, weighing the MCP's always-on tool-schema **token cost**. Otherwise prefer the
  CLI (no install) or a thin skill that drives it. Map the gap to the right form: a skill
  for a procedure, a plugin for a bundle, an MCP for a live-data/tool gap a CLI can't fill.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py -v`
Expected: PASS (new test green; existing `test_capability_scout_*` still green — they assert `work_type`, `verify`, `never`+`invent`, `well-known`, none of which this change removes).

- [ ] **Step 5: Commit**

```bash
git add skills/recommend-actions/prompts/capability_scout.md skills/recommend-actions/scripts/test_prompts.py
git commit -m "fix(capability-scout): CLI-first; an MCP must earn its place over an existing CLI"
```

---

### Task 3: actions_server.py — the selection server

**Files:**
- Create: `skills/recommend-actions/scripts/actions_server.py`
- Test: `skills/recommend-actions/scripts/test_actions_server.py`

**Interfaces:**
- Produces:
  - `set_selected(doc: dict, action_id: str, selected: bool) -> bool` — flips that action's `apply.status` to `"selected"` (True) or `"pending"` (False); returns whether the id was found.
  - `ActionsHandler` — `http.server.SimpleHTTPRequestHandler` subclass; `GET /__actions__/health` → `{"root","pid"}`; `POST /__actions__/select` (header `X-Actions-Select: 1`, body `{"id","selected"}`) flips status in `<root>/actions.json`.
  - `DEFAULT_PORT = 4577`, `PORT_ATTEMPTS = 10` (consumed by Task 5's `render.py`).

- [ ] **Step 1: Write the failing test (pure function)**

Create `skills/recommend-actions/scripts/test_actions_server.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_actions_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'actions_server'`.

- [ ] **Step 3: Create the server**

Create `skills/recommend-actions/scripts/actions_server.py`:

```python
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
```

- [ ] **Step 4: Run to verify the pure-function tests pass**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_actions_server.py -v`
Expected: PASS (`test_set_selected_flips`, `test_set_selected_unknown_returns_false`).

- [ ] **Step 5: Write the failing live-server tests**

Append to `skills/recommend-actions/scripts/test_actions_server.py`:

```python
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
```

- [ ] **Step 6: Run to verify all server tests pass**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_actions_server.py -v`
Expected: PASS (7 tests: 2 pure + health + flip + header-guard + unknown-id + unknown-path). The fixture's `ThreadingHTTPServer` is shut down each test; no port leaks.

- [ ] **Step 7: Commit**

```bash
git add skills/recommend-actions/scripts/actions_server.py skills/recommend-actions/scripts/test_actions_server.py
git commit -m "feat(recommend-actions): actions_server.py persists Apply selection into actions.json"
```

---

### Task 4: action_card — interactive Apply affordance

**Files:**
- Modify: `skills/_shared/coach_theme.py` (`action_card`, ~lines 233–250; add `_apply_affordance` helper)
- Test: `skills/_shared/test_coach_theme.py` (`test_action_card_family_color_and_drawer`)

**Interfaces:**
- Consumes: nothing.
- Produces: `action_card(... , apply_kind="", apply_preview="", action_id="", status="pending")` now emits, for non-`advisory` actionable kinds, a `<button class="apply-btn" data-action-id=… aria-pressed=…>` plus a demoted `<details class="apply"><summary>View change</summary>` disclosure; the card root carries `data-action-id` and `data-status`. `advisory` kind emits **no** button. (Button/toast CSS is supplied by Task 5's runtime block; the `details.apply` CSS already exists in `STYLE`.)

- [ ] **Step 1: Rewrite the failing test**

Replace `test_action_card_family_color_and_drawer` in `skills/_shared/test_coach_theme.py` with:

```python
def test_action_card_has_apply_button_and_demoted_preview():
    a = ct.action_card("Install X", "acquire", "low", "Because reasons.",
                       impact_html=ct.impact_figure("2", "avoided"),
                       source_html='verified · <a href="https://ex.com">src</a>',
                       evidence_html=ct.evidence("sig", "q"),
                       apply_kind="run_command", apply_preview="/plugin install x",
                       action_id="install-x", status="pending")
    assert 'class="acard"' in a and "<h3>Install X</h3>" in a
    assert "var(--c-acquire)" in a and "low effort" in a
    assert 'data-action-id="install-x"' in a            # id on the card
    assert 'class="apply-btn"' in a and 'aria-pressed="false"' in a   # CTA button
    assert ">Apply<" in a                               # pending label
    assert "View change" in a and "/plugin install x" in a   # preview demoted, still present
    assert "Apply — run_command" not in a               # old drawer gone


def test_action_card_selected_status_renders_pressed():
    a = ct.action_card("X", "config", "low", "r", apply_kind="archive",
                       apply_preview="/path", action_id="x", status="selected")
    assert 'aria-pressed="true"' in a
    assert "Selected for application" in a


def test_action_card_advisory_has_no_button():
    a = ct.action_card("Habit", "behavior", "low", "guidance",
                       apply_kind="advisory", apply_preview="do the thing",
                       action_id="hab", status="pending")
    assert "apply-btn" not in a                         # nothing to execute
    assert "guidance" in a
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd skills/_shared && python -m pytest test_coach_theme.py -v`
Expected: FAIL (`action_card()` has no `action_id`/`status` params → `TypeError`).

- [ ] **Step 3: Implement the affordance**

In `skills/_shared/coach_theme.py`, add a module-level helper just above `action_card`:

```python
_APPLY_LABEL = {"pending": "Apply", "selected": "✓ Selected for application",
                "applied": "Applied ✓", "skipped": "Skipped"}


def _apply_affordance(action_id, apply_kind, apply_preview, status):
    """Apply button (primary CTA) + a demoted 'View change' disclosure. advisory: no button."""
    if not apply_kind or apply_kind == "advisory":
        return ""
    st = status if status in _APPLY_LABEL else "pending"
    pressed = "true" if st == "selected" else "false"
    disabled = " disabled" if st in ("applied", "skipped") else ""
    btn = (f'<button class="apply-btn" type="button" data-action-id="{esc(action_id)}" '
           f'data-apply-kind="{esc(apply_kind)}" aria-pressed="{pressed}"{disabled}>'
           f'{esc(_APPLY_LABEL[st])}</button>')
    detail = (f'<details class="apply"><summary>View change</summary>'
              f'<pre>{esc(apply_preview)}</pre></details>') if apply_preview else ""
    return f'<div class="apply-row">{btn}</div>{detail}'
```

Then replace the body of `action_card` (the `drawer` block and the final return) with:

```python
def action_card(title, family, effort, rationale_html, *, impact_html="",
                source_html="", evidence_html="", apply_kind="", apply_preview="",
                action_id="", status="pending"):
    fam = (f'<span class="tag fam"><span class="fdot" style="background:var(--c-{esc(family)})">'
           f'</span>{esc(family)}</span>')
    eff = f'<span class="tag">{esc(effort)} effort</span>' if effort else ""
    foot_bits = []
    if impact_html:
        foot_bits.append(impact_html)
    if source_html:
        foot_bits.append(f'<span class="src">{source_html}</span>')
    foot = f'<div class="foot">{"".join(foot_bits)}</div>' if foot_bits else ""
    apply_html = _apply_affordance(action_id, apply_kind, apply_preview, status)
    return (f'<div class="acard" data-action-id="{esc(action_id)}" data-status="{esc(status)}">'
            f'<div class="acard-top"><h3>{esc(title)}</h3>'
            f'<div class="tags">{fam}{eff}</div></div>'
            f'<p class="rat">{rationale_html}</p>{foot}{evidence_html}{apply_html}</div>')
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd skills/_shared && python -m pytest test_coach_theme.py -v`
Expected: PASS (3 new action_card tests green; the rest of `test_coach_theme.py` unaffected).

- [ ] **Step 5: Commit**

```bash
git add skills/_shared/coach_theme.py skills/_shared/test_coach_theme.py
git commit -m "feat(coach_theme): action_card emits an Apply toggle; demote the diff to 'View change'"
```

---

### Task 5: render.py — thread id/status, embed runtime, serve & open

**Files:**
- Modify: `skills/recommend-actions/scripts/render.py` (`_card`, `render_html`, `main`; add `APPLY_RUNTIME` + server helpers)
- Test: `skills/recommend-actions/scripts/test_render.py`

**Interfaces:**
- Consumes: `coach_theme.action_card(..., action_id, status)` (Task 4); `actions_server.DEFAULT_PORT`, `actions_server.PORT_ATTEMPTS` (Task 3).
- Produces: `render_html(doc)` (still pure) now embeds the apply-runtime block and passes each action's `id`/`status` to its card; `main()` opens the report through `actions_server.py` (falls back to `file://` if the server can't start).

- [ ] **Step 1: Write the failing tests**

Add to `skills/recommend-actions/scripts/test_render.py`:

```python
def test_html_card_has_apply_button_and_runtime():
    html = render.render_html(DOC)
    assert 'data-action-id="capture-coa"' in html        # id threaded onto the card
    assert 'class="apply-btn"' in html                   # interactive CTA
    assert 'id="ac-apply-runtime"' in html               # embedded toggle script
    assert "/__actions__/select" in html                 # runtime posts to the server
    assert "View change" in html                         # diff demoted, not the headline
    assert "Apply — edit_file" not in html               # old drawer label gone
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_render.py::test_html_card_has_apply_button_and_runtime -v`
Expected: FAIL (`data-action-id` not yet emitted; no runtime block).

- [ ] **Step 3: Thread id/status through `_card`**

In `render.py`, in `_card(a)`, the final `return coach_theme.action_card(...)` call passes `apply_kind`/`apply_preview`. Add the two new kwargs (the function already binds `apply_b = a.get("apply", {})`):

```python
    return coach_theme.action_card(
        a.get("title", ""), a.get("family", ""), a.get("effort", ""),
        _esc(a.get("rationale", "")),
        impact_html=impact_html, source_html=source_html, evidence_html=ev,
        apply_kind=apply_b.get("kind", ""), apply_preview=apply_b.get("preview", ""),
        action_id=a.get("id", ""), status=apply_b.get("status", "pending"))
```

- [ ] **Step 4: Add the runtime constant and embed it**

In `render.py`, add `import actions_server` next to the other imports (it lives in this same dir; importing it has no side effects), and add the runtime constant near the top-level constants:

```python
import actions_server  # same dir; provides DEFAULT_PORT / PORT_ATTEMPTS and is the served backend

APPLY_RUNTIME = """
<style id="ac-apply-style">
  .apply-row{margin-top:13px}
  .apply-btn{font:500 13px var(--sans);cursor:pointer;border:1.5px solid var(--accent);
    color:var(--accent-deep);background:var(--surface);border-radius:999px;padding:6px 15px;
    transition:background .15s,color .15s}
  .apply-btn:hover{background:var(--inset)}
  .apply-btn[aria-pressed="true"]{background:var(--accent);color:#fff;border-color:var(--accent)}
  .apply-btn:disabled{cursor:default;border-color:var(--line-2);color:var(--ink-3);background:var(--surface-2)}
  #ac-status{position:fixed;bottom:14px;right:14px;z-index:100;font:12px var(--sans);
    background:var(--ink);color:#fff;padding:6px 12px;border-radius:6px;opacity:0;
    transition:opacity .3s;pointer-events:none}
</style>
<script id="ac-apply-runtime">
(function(){
  'use strict';
  var LABEL={selected:'✓ Selected for application',pending:'Apply'};
  function toast(msg){
    var el=document.getElementById('ac-status');
    if(!el){el=document.createElement('div');el.id='ac-status';document.body.appendChild(el);}
    el.textContent=msg;el.style.opacity='1';
    clearTimeout(el._t);el._t=setTimeout(function(){el.style.opacity='0';},3600);
  }
  document.addEventListener('click',function(e){
    var btn=e.target.closest&&e.target.closest('.apply-btn');
    if(!btn||btn.disabled)return;
    if(location.protocol!=='http:'&&location.protocol!=='https:'){
      toast('Selection not saved — open this report via render.py so the server is running');
      return;
    }
    var id=btn.getAttribute('data-action-id');
    var selected=btn.getAttribute('aria-pressed')!=='true';   // toggle
    btn.disabled=true;
    fetch('/__actions__/select',{method:'POST',
      headers:{'Content-Type':'application/json','X-Actions-Select':'1'},
      body:JSON.stringify({id:id,selected:selected})})
     .then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();})
     .then(function(d){
       btn.setAttribute('aria-pressed',d.status==='selected'?'true':'false');
       btn.textContent=LABEL[d.status]||'Apply';
       var card=btn.closest('.acard');if(card)card.setAttribute('data-status',d.status);
       btn.disabled=false;
       toast(d.status==='selected'?'Selected ✓':'Removed from selection');
     })
     .catch(function(err){btn.disabled=false;toast('Save failed — '+err.message);});
  });
})();
</script>
"""
```

> Note: in a normal Python string, `'✓'` is the ✓ character — that is intended (the JS label shows ✓). The `id="ac-apply-runtime"` is the stable grep/upgrade handle.

Then, in `render_html`, append the runtime as the final body block — change the end of the function from:

```python
    blocks.append(coach_theme.section(
        "·", "Considered but not recommended",
        "<ul style='list-style:none;padding:0;font-size:13.5px'>%s</ul>" % nr_items))
    return coach_theme.page(
```

to:

```python
    blocks.append(coach_theme.section(
        "·", "Considered but not recommended",
        "<ul style='list-style:none;padding:0;font-size:13.5px'>%s</ul>" % nr_items))
    blocks.append(APPLY_RUNTIME)
    return coach_theme.page(
```

- [ ] **Step 5: Run to verify the render test passes**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_render.py -v`
Expected: PASS — the new test plus existing ones (`test_html_has_lanes_cards_and_banner`, `test_html_escapes_and_handles_empty`, etc. don't assert the old drawer text, so they stay green).

- [ ] **Step 6: Wire `main()` to serve & open**

Add `import re` to the imports. Add the server helpers above `main()`:

```python
def _server_url(port):
    return f"http://127.0.0.1:{port}/actions.html"


def _find_or_start_server(profile_dir):
    """Reuse a running actions_server for this dir, else start one. Return port or None."""
    import http.client
    import subprocess
    real = os.path.realpath(profile_dir)
    for port in range(actions_server.DEFAULT_PORT,
                      actions_server.DEFAULT_PORT + actions_server.PORT_ATTEMPTS):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=0.3)
        try:
            conn.request("GET", "/__actions__/health")
            r = conn.getresponse()
            if r.status == 200 and os.path.realpath(json.loads(r.read()).get("root", "")) == real:
                return port
        except OSError:
            pass
        finally:
            conn.close()
    server_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "actions_server.py")
    proc = subprocess.Popen([sys.executable, server_py, "--root", real],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:                       # read the startup line for the actual port
        m = re.search(r"http://127\.0\.0\.1:(\d+)/", line)
        if m:
            return int(m.group(1))
    return None
```

Then change the tail of `main()` (the `if not args.no_open:` block) from:

```python
    sys.stderr.write(f"\nWrote {out}\n")
    if not args.no_open:
        webbrowser.open(f"file://{os.path.abspath(out)}")
```

to:

```python
    sys.stderr.write(f"\nWrote {out}\n")
    if args.no_open:
        return
    profile_dir = os.path.dirname(os.path.abspath(out))
    port = _find_or_start_server(profile_dir)
    if port:
        webbrowser.open(_server_url(port))
        sys.stderr.write(f"Serving at {_server_url(port)} — Apply selections persist to actions.json\n")
    else:
        webbrowser.open(f"file://{os.path.abspath(out)}")
        sys.stderr.write("Could not start the selection server; opened read-only via file://\n")
```

> `--no-open` returns before any server work, so `test_cli_writes_html` (which passes `--no-open`) never spawns a process.

- [ ] **Step 7: Run the full recommend-actions suite**

Run: `cd skills/recommend-actions && python -m pytest scripts/ -v`
Expected: PASS (render, prompts, server, cache, load, build, integration all green). `test_cli_writes_html` still writes the file with `--no-open` and starts no server.

- [ ] **Step 8: Manual smoke (one-time, not a unit test)**

Run against an existing report (use any profile dir that has an `actions.json`):
```bash
cd skills/recommend-actions && python scripts/render.py "$HOME/.claude/profiles/<some-slug>/actions.json"
```
Verify: the browser opens at `http://127.0.0.1:4577/actions.html`; clicking **Apply** flips the button to **✓ Selected for application** and a toast says "Selected ✓"; re-reading the file shows that action's `apply.status == "selected"`; clicking again reverts to `pending`. Then `Ctrl-C` is not needed (the server is a detached child; leave it or `pkill -f actions_server.py`).

- [ ] **Step 9: Commit**

```bash
git add skills/recommend-actions/scripts/render.py skills/recommend-actions/scripts/test_render.py
git commit -m "feat(recommend-actions): render Apply toggles and open actions.html via the selection server"
```

---

### Task 6: /perform-actions — read the selection

**Files:**
- Modify: `skills/perform-actions/scripts/load_actions.py:main` (add `n_selected`)
- Modify: `skills/perform-actions/scripts/test_load_actions.py`
- Modify: `skills/perform-actions/SKILL.md` (Step 2 — filter to selected + empty fallback)
- Modify: `skills/recommend-actions/SKILL.md` (Step 4 — note the report is served so Apply persists)

**Interfaces:**
- Consumes: the `selected` status written by the server (Task 3).
- Produces: `load_actions.py` CLI output gains `n_selected`; the perform-actions walk filters to `status=="selected"` with a walk-all fallback.

- [ ] **Step 1: Write the failing test**

In `skills/perform-actions/scripts/test_load_actions.py`, update `test_cli_emits_json` to also assert `n_selected`, and add a selected-count test:

```python
def test_cli_emits_json(tmp_path):
    cwd = _write(tmp_path)
    out = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "load_actions.py"),
         cwd, "--profiles-root", str(tmp_path / "profiles")],
        capture_output=True, text=True, check=True).stdout
    doc = json.loads(out)
    assert doc["n_actions"] == 1 and doc["path"].endswith("actions.json")
    assert doc["n_selected"] == 0          # DOC's only action is status "pending"


def test_cli_counts_selected(tmp_path):
    cwd = "/Volumes/sel"
    d = tmp_path / "profiles" / la.encode_cwd(cwd)
    d.mkdir(parents=True)
    (d / "actions.json").write_text(json.dumps({"actions": [
        {"id": "s1", "apply": {"kind": "archive", "status": "selected"}},
        {"id": "p1", "apply": {"kind": "edit_file", "status": "pending"}}]}))
    out = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "load_actions.py"),
         cwd, "--profiles-root", str(tmp_path / "profiles")],
        capture_output=True, text=True, check=True).stdout
    assert json.loads(out)["n_selected"] == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd skills/perform-actions && python -m pytest scripts/test_load_actions.py -v`
Expected: FAIL (`KeyError: 'n_selected'`).

- [ ] **Step 3: Add `n_selected` to `load_actions.py`**

In `load_actions.py`, replace the success-branch `print(...)` in `main()`:

```python
    print(json.dumps({"slug": res["slug"], "dir": res["dir"], "path": res["path"],
                      "n_actions": len(res["doc"].get("actions", []))}))
```

with:

```python
    actions = res["doc"].get("actions", [])
    n_selected = sum(1 for a in actions
                     if a.get("apply", {}).get("status") == "selected")
    print(json.dumps({"slug": res["slug"], "dir": res["dir"], "path": res["path"],
                      "n_actions": len(actions), "n_selected": n_selected}))
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd skills/perform-actions && python -m pytest scripts/test_load_actions.py -v`
Expected: PASS (both updated/new tests green; the rest unaffected).

- [ ] **Step 5: Update perform-actions SKILL.md Step 2 (prose)**

In `skills/perform-actions/SKILL.md`, replace the first sentence of **Step 2 — Walk + route**:

```
Walk `doc.actions` in `do_now` → `consider` → `fyi` order. For each action, show its
`title`, `rationale`, and `apply.preview`, then ask whether to apply it. Only on an
explicit **yes**, route by `apply.kind`:
```

with:

```
First filter to the actions the user **selected** in `actions.html`:
`selected = [a for a in doc.actions if a.get("apply", {}).get("status") == "selected"]`.
- If `selected` is **empty** (they opened the report and picked nothing, or it predates
  the Apply UI), say no actions are marked *Selected for application*, and offer to either
  reopen `actions.html` to choose, or walk **all** `doc.actions` this once.
- Otherwise walk `selected` in `do_now` → `consider` → `fyi` order.
For each walked action, show its `title`, `rationale`, and `apply.preview`, then ask
whether to apply it (selection pre-filters the queue; this per-action yes/no is still
required). Only on an explicit **yes**, route by `apply.kind`:
```

- [ ] **Step 6: Update recommend-actions SKILL.md Step 4 (prose)**

In `skills/recommend-actions/SKILL.md`, Step 4, after the sentence ending `(opens \`actions.html\`).`, append:

```
Opening serves the report from a small local `actions_server.py`, so clicking **Apply**
on a card persists that choice into `actions.json` (sets `apply.status: "selected"`) —
which `/perform-actions` then reads to pre-filter what it applies.
```

- [ ] **Step 7: Run both skills' suites**

Run: `cd skills && python -m pytest perform-actions/scripts/ recommend-actions/scripts/ -v`
Expected: PASS across both.

- [ ] **Step 8: Commit**

```bash
git add skills/perform-actions/scripts/load_actions.py skills/perform-actions/scripts/test_load_actions.py skills/perform-actions/SKILL.md skills/recommend-actions/SKILL.md
git commit -m "feat(perform-actions): apply only Selected actions; count n_selected; doc the round-trip"
```

---

### Task 7: Regenerate the cadel-mono-repo report (runtime step)

Not a code/test task — a guided runtime action, done after Tasks 1–6 are merged and `python -m pytest skills/` is fully green. It re-runs the coach so the live report reflects the fixed judgment and the new interactive UI. It requires the user's consent gate (and an optional live web lookup), so drive it interactively, do not script it silently.

- [ ] **Step 1: Confirm the whole suite is green**

Run: `cd /Volumes/Sources/claudecoach && python -m pytest skills/ -q`
Expected: all pass.

- [ ] **Step 2: Re-run the coach for cadel-mono-repo**

Invoke `/recommend-actions` for `/Volumes/Sources/cadel-mono-repo` (its own consent + optional live lookup). This overwrites `~/.claude/profiles/-Volumes-Sources-cadel-mono-repo/actions.json` + `actions.html`.

- [ ] **Step 3: Verify the judgment fixes landed**

Confirm in the regenerated report: **no** "archive the redundant personal …" cards for `karpathy-guidelines` / `frontend-design` / `commit-push-pr`; MCP suggestions for capabilities already covered by `gh` / `docker` CLIs are gone or justified against the CLI. Open it and confirm the **Apply** buttons persist selections.

---

## Self-Review

**1. Spec coverage**
- Selection round-trip / `actions_server.py` → Task 3. ✔
- `apply.status` gains `selected` → Task 3 (`set_selected`), additive. ✔
- Apply button CTA + demoted "View change" + advisory-no-button → Task 4. ✔
- Apply-runtime block + serve/open → Task 5. ✔
- `/perform-actions` filters selected + empty fallback + `n_selected` → Task 6. ✔
- config_doctor personal-scope fix → Task 1; capability_scout CLI-first → Task 2. ✔
- Regenerate cadel-mono-repo → Task 7. ✔
- `set_status.py` untouched → confirmed (server owns `selected↔pending`). ✔
- Tests LLM-free/offline → all use stdlib + loopback only. ✔

**2. Placeholder scan:** none — every code/edit step shows full content and exact location.

**3. Type consistency:** `set_selected(doc, action_id, selected)→bool`, `_apply_affordance(action_id, apply_kind, apply_preview, status)→str`, `action_card(..., apply_kind, apply_preview, action_id, status)`, `_find_or_start_server(profile_dir)→int|None`, `_server_url(port)→str`. `DEFAULT_PORT`/`PORT_ATTEMPTS` are defined once in `actions_server.py` and referenced via `actions_server.` in `render.py` (no drift). The runtime POSTs `{"id","selected"}` and the server expects exactly those keys; the server returns `{"id","status"}` and the JS reads `d.status`. Consistent.

## Execution Handoff

After saving, offer the two execution options (subagent-driven vs inline).
