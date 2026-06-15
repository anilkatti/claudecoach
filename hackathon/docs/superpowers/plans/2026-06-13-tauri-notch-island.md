# Tauri Notch-Island Placeholder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Tauri v2 macOS app that renders a Dynamic-Island-style black pill hugging the MacBook notch, collapsed by default and auto-expanded/collapsed by the backend.

**Architecture:** A single borderless, transparent, always-on-top, click-through Tauri window parked at top-center and raised above the menu bar via a small piece of native Rust (`objc2-app-kit`). The Rust backend owns island state: a `set_island_state` command and a demo driver both emit an `island://state` event; the vanilla HTML/CSS/JS frontend listens and animates the pill between collapsed and expanded with CSS. The native window never resizes — the pill animates inside it.

**Tech Stack:** Tauri v2, Rust, `objc2-app-kit` 0.3.2, vanilla HTML/CSS/JS (no bundler, `window.__TAURI__` global), pnpm.

**API grounding (verified against current docs):**
- Emit from Rust: `use tauri::Emitter; app.emit("event", payload)` — [Calling the Frontend from Rust](https://v2.tauri.app/develop/calling-frontend/)
- NSWindow access + objc2-app-kit pattern — [Window Customization](https://v2.tauri.app/learn/window-customization/)
- `WebviewWindow::set_ignore_cursor_events(&self, ignore: bool) -> Result<()>`, `primary_monitor`, `set_position`, `set_always_on_top`, `show`, `scale_factor` — [docs.rs WebviewWindow](https://docs.rs/tauri/latest/tauri/webview/struct.WebviewWindow.html)
- `NSWindow::setLevel(&self, level: NSWindowLevel)` — [docs.rs NSWindow](https://docs.rs/objc2-app-kit/latest/objc2_app_kit/struct.NSWindow.html)

**Note on testing:** This is a GUI + native-window demo. Pure logic is thin, so automated testing is limited to one Rust unit test on the event payload shape (the contract the frontend depends on). The window/visual behaviors are verified manually against the spec's 6 success criteria — each such step lists the exact observation expected.

---

## File Structure

The Tauri app lives in a new `island/` subdirectory of the repo (the scaffolder cannot write into the non-empty repo root). Files created/modified after scaffolding:

- `island/src-tauri/tauri.conf.json` — window config (borderless/transparent/on-top), `macOSPrivateApi`, `withGlobalTauri`. **Modified.**
- `island/src-tauri/Cargo.toml` — add `macos-private-api` tauri feature + `objc2-app-kit` macOS dep. **Modified.**
- `island/src-tauri/src/lib.rs` — window placement, native level-raise, `set_island_state` + `island_ready` commands, demo driver, unit test. **Rewritten.**
- `island/src-tauri/capabilities/default.json` — ensure event-listen permission. **Modified.**
- `island/index.html` — collapsed/expanded pill markup. **Rewritten.**
- `island/src/styles.css` — pill styling + collapsed⇄expanded transitions. **Rewritten.**
- `island/src/main.js` — listen for `island://state`, invoke `island_ready`. **Rewritten.**

Untouched scaffolded files: `main.rs`, `build.rs`, `icons/`, `package.json`, bundle config.

---

## Task 0: Install the Rust toolchain (prerequisite)

**Files:** none (environment setup)

> Rust is not installed. Node 25, pnpm 9, and Xcode Command Line Tools are already present. This step downloads and runs the official `rustup` installer — confirm with the user before running (network + toolchain install).

- [ ] **Step 1: Install Rust via rustup (non-interactive)**

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
```

- [ ] **Step 2: Load cargo into the current shell and verify**

```bash
source "$HOME/.cargo/env"
rustc --version && cargo --version
```

Expected: prints `rustc 1.x.x ...` and `cargo 1.x.x ...` (no "command not found").

---

## Task 1: Scaffold the Tauri vanilla app

**Files:** Create: `island/` (entire Tauri vanilla project)

- [ ] **Step 1: Scaffold with create-tauri-app**

From the repo root (`/Volumes/Sources/claudecoach`):

```bash
pnpm create tauri-app island --template vanilla --manager pnpm
```

If the flags are rejected or it prompts interactively, answer: project name `island`, package manager `pnpm`, UI template `Vanilla`, language `JavaScript`. The goal is a no-bundler vanilla JS Tauri v2 project in `island/`.

- [ ] **Step 2: Install dependencies**

```bash
cd island && pnpm install
```

Expected: installs `@tauri-apps/cli` and `@tauri-apps/api` into `island/node_modules`.

- [ ] **Step 3: Verify the default app builds and runs**

```bash
cd island && pnpm tauri dev
```

Expected: Rust compiles (first build is slow), and a normal window opens showing the default Tauri greet template. Confirm it launched, then stop it (Ctrl-C). This proves the toolchain + scaffold work before we customize.

- [ ] **Step 4: Commit the scaffold**

```bash
git add island
git commit -m "Scaffold vanilla Tauri v2 app in island/"
```

---

## Task 2: Configure the window (borderless, transparent, on-top)

**Files:** Modify: `island/src-tauri/tauri.conf.json`, `island/src-tauri/Cargo.toml`

- [ ] **Step 1: Edit the `app` section of `tauri.conf.json`**

Replace the `app` object's `windows` array with a single configured window, and add `macOSPrivateApi` + `withGlobalTauri`. The `app` object should contain (keep any existing `security` block as-is):

```json
"app": {
  "withGlobalTauri": true,
  "macOSPrivateApi": true,
  "windows": [
    {
      "label": "main",
      "title": "Island",
      "width": 360,
      "height": 220,
      "resizable": false,
      "decorations": false,
      "transparent": true,
      "alwaysOnTop": true,
      "shadow": false,
      "skipTaskbar": true,
      "visible": false
    }
  ],
  "security": {
    "csp": null
  }
}
```

> `visible: false` lets us position the window before showing it. `transparent: true` on macOS requires `macOSPrivateApi: true` (next step adds the matching Cargo feature so the two stay consistent — a mismatch is the documented error in tauri#11142).

- [ ] **Step 2: Enable the `macos-private-api` feature in `Cargo.toml`**

In `island/src-tauri/Cargo.toml`, change the `tauri` dependency to include the feature. Find the line like `tauri = { version = "2", features = [] }` and make it:

```toml
tauri = { version = "2", features = ["macos-private-api"] }
```

- [ ] **Step 3: Verify it still builds**

```bash
cd island && pnpm tauri dev
```

Expected: compiles and runs. The window is now borderless and 360×220, positioned wherever the OS placed it (top-center positioning comes in Task 3). It may currently show the default greet content with a transparent/odd background — that's expected at this stage. Stop it (Ctrl-C).

> If the build errors with a message about `tauri` features not matching the config allowlist, the feature in Step 2 and `macOSPrivateApi` in Step 1 are out of sync — re-check both are set.

- [ ] **Step 4: Commit**

```bash
git add island/src-tauri/tauri.conf.json island/src-tauri/Cargo.toml
git commit -m "Configure borderless transparent always-on-top window"
```

---

## Task 3: Native window placement (top-center, above menu bar, click-through)

**Files:** Modify: `island/src-tauri/src/lib.rs`, `island/src-tauri/Cargo.toml`

- [ ] **Step 1: Add the macOS native dependency to `Cargo.toml`**

Append to `island/src-tauri/Cargo.toml` (target-specific so it only builds on macOS):

```toml
[target."cfg(target_os = \"macos\")".dependencies]
objc2-app-kit = { version = "0.3.2", features = ["NSWindow"] }
```

- [ ] **Step 2: Rewrite `lib.rs` with setup + placement (commands come in Task 4)**

Replace the entire contents of `island/src-tauri/src/lib.rs` with:

```rust
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let window = app.get_webview_window("main").expect("main window exists");
            position_island(&window);
            let _ = window.set_ignore_cursor_events(true);
            let _ = window.set_always_on_top(true);
            #[cfg(target_os = "macos")]
            raise_above_menu_bar(&window);
            let _ = window.show();
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

/// Park the window at the top-center of the primary display, flush to the top edge.
fn position_island(window: &tauri::WebviewWindow) {
    if let Ok(Some(monitor)) = window.primary_monitor() {
        let scale = monitor.scale_factor();
        let screen = monitor.size().to_logical::<f64>(scale);
        let win_w = 360.0_f64; // keep in sync with width in tauri.conf.json
        let x = (screen.width - win_w) / 2.0;
        let _ = window.set_position(tauri::LogicalPosition::new(x, 0.0));
    }
}

/// Raise the window above the macOS menu bar so the pill is visible over it.
#[cfg(target_os = "macos")]
fn raise_above_menu_bar(window: &tauri::WebviewWindow) {
    use objc2_app_kit::NSWindow;
    if let Ok(ptr) = window.ns_window() {
        let ns_window = unsafe { &*(ptr as *mut NSWindow) };
        // NSWindowLevel is a type alias for NSInteger (isize).
        // 25 == NSStatusWindowLevel, which sits above the menu bar (level 24).
        // If the menu bar still covers the pill, bump to 101 (pop-up menu level).
        let level: objc2_app_kit::NSWindowLevel = 25;
        ns_window.setLevel(level);
    }
}
```

> If Step 3 fails to compile with "expected `NSWindowLevel`, found integer", `NSWindowLevel` is a newtype in this crate version — change the assignment to `let level = objc2_app_kit::NSWindowLevel(25);`.

- [ ] **Step 3: Build and verify placement**

```bash
cd island && pnpm tauri dev
```

Expected observations:
1. A small window sits at the **top-center** of the screen, its top edge flush with the screen top, overlapping the notch area.
2. It is **visible over the menu bar** (not hidden behind it).
3. It is **click-through**: clicking menu bar items on the left/right of the notch still works.

Content is still the default greet markup — styling is Task 5. Stop it (Ctrl-C).

- [ ] **Step 4: Commit**

```bash
git add island/src-tauri/src/lib.rs island/src-tauri/Cargo.toml
git commit -m "Place window top-center, above menu bar, click-through"
```

---

## Task 4: Island state command, event, and demo driver

**Files:** Modify: `island/src-tauri/src/lib.rs`

- [ ] **Step 1: Add the payload type, commands, demo driver, and unit test**

Edit `island/src-tauri/src/lib.rs`. Add `Emitter` to the imports and register the commands. The top `use` line becomes:

```rust
use tauri::{AppHandle, Emitter, Manager};
```

Change the builder to register the invoke handler — insert this line before `.setup(`:

```rust
        .invoke_handler(tauri::generate_handler![set_island_state, island_ready])
```

Add these items to the file (after the `run` function):

```rust
#[derive(Clone, serde::Serialize)]
struct IslandState {
    state: String,
}

/// Programmatic control point: any backend code can flip the island state.
#[tauri::command]
fn set_island_state(app: AppHandle, state: String) {
    let _ = app.emit("island://state", IslandState { state });
}

/// The frontend calls this once it has registered its listener.
/// We then drive a one-shot demo so the auto-expand is visible immediately.
#[tauri::command]
fn island_ready(app: AppHandle) {
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_millis(2000));
        let _ = app.emit("island://state", IslandState { state: "expanded".into() });
        std::thread::sleep(std::time::Duration::from_millis(4000));
        let _ = app.emit("island://state", IslandState { state: "collapsed".into() });
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn island_state_serializes_with_state_field() {
        let json = serde_json::to_string(&IslandState { state: "expanded".into() }).unwrap();
        assert_eq!(json, r#"{"state":"expanded"}"#);
    }
}
```

> `serde` and `serde_json` are already dependencies in the scaffolded `Cargo.toml`. The unit test pins the payload shape (`{"state": ...}`) that the frontend reads as `event.payload.state`.

- [ ] **Step 2: Run the unit test to verify it passes**

```bash
cd island/src-tauri && cargo test island_state_serializes_with_state_field
```

Expected: `test tests::island_state_serializes_with_state_field ... ok`.

- [ ] **Step 3: Commit**

```bash
git add island/src-tauri/src/lib.rs
git commit -m "Add island state command, event, and demo driver"
```

---

## Task 5: Frontend island UI

**Files:** Rewrite: `island/index.html`, `island/src/styles.css`, `island/src/main.js`

- [ ] **Step 1: Replace `island/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="stylesheet" href="/src/styles.css" />
    <title>Island</title>
  </head>
  <body>
    <div id="island" data-state="collapsed">
      <div class="collapsed-content">
        <span class="dot"></span>
        <span class="label">Island</span>
      </div>
      <div class="expanded-content">
        <div class="title">Placeholder</div>
        <div class="subtitle">Auto-expanded by the app</div>
      </div>
    </div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

- [ ] **Step 2: Replace `island/src/styles.css`**

```css
:root { color-scheme: dark; }
* { box-sizing: border-box; }

html, body {
  margin: 0;
  height: 100%;
  background: transparent;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
  -webkit-user-select: none;
  user-select: none;
}

#island {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  background: #000;
  /* Top flush to the screen edge; only the bottom corners round (the notch look). */
  border-radius: 0 0 18px 18px;
  overflow: hidden;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
  transition:
    width 0.45s cubic-bezier(0.22, 1, 0.36, 1),
    height 0.45s cubic-bezier(0.22, 1, 0.36, 1),
    border-radius 0.45s ease;
}

#island[data-state="collapsed"] {
  width: 200px;
  height: 34px;
  border-radius: 0 0 17px 17px;
}

#island[data-state="expanded"] {
  width: 320px;
  height: 170px;
  border-radius: 0 0 34px 34px;
}

.collapsed-content,
.expanded-content {
  position: absolute;
  inset: 0;
  color: #fff;
  transition: opacity 0.25s ease;
}

.collapsed-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
}

.dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #34c759;
}

.expanded-content {
  padding: 46px 22px 18px;
  opacity: 0;
}

.title { font-size: 17px; font-weight: 600; }
.subtitle { margin-top: 4px; font-size: 13px; color: rgba(255, 255, 255, 0.6); }

#island[data-state="expanded"] .collapsed-content { opacity: 0; }
#island[data-state="expanded"] .expanded-content { opacity: 1; }
```

- [ ] **Step 3: Replace `island/src/main.js`**

```js
// Vanilla template (no bundler) — use the global Tauri API.
const { listen } = window.__TAURI__.event;
const { invoke } = window.__TAURI__.core;

const island = document.getElementById("island");

async function init() {
  await listen("island://state", (event) => {
    const state = event.payload?.state;
    if (state === "collapsed" || state === "expanded") {
      island.dataset.state = state;
    }
  });
  // Listener is ready — let the backend drive the demo expand/collapse.
  await invoke("island_ready");
}

init();
```

- [ ] **Step 4: Ensure event-listen permission**

Open `island/src-tauri/capabilities/default.json`. Confirm its `permissions` array contains `"core:default"`. To be safe, also add `"core:event:default"` so `listen()` is allowed. Example result:

```json
"permissions": [
  "core:default",
  "core:event:default",
  "opener:default"
]
```

(Keep any other entries the scaffolder added, e.g. `opener:default`.)

- [ ] **Step 5: Run and verify all success criteria**

```bash
cd island && pnpm tauri dev
```

Expected observations (the spec's success criteria):
1. **Launches** with no errors in the terminal or webview console.
2. A **black pill hugs the notch** at top-center, visible over the menu bar, with a green dot + "Island" label.
3. Menu bar items remain **clickable** (window is click-through).
4. After ~2s the pill **auto-expands** to show "Placeholder / Auto-expanded by the app", then **collapses** after ~4s — with no user interaction.
5. (Optional manual check) With the app running, in the webview devtools console run `window.__TAURI__.core.invoke('set_island_state', { state: 'expanded' })` and confirm the pill expands on demand; `{ state: 'collapsed' }` collapses it.
6. **⌘Q quits** cleanly.

> If the console shows an event permission error, re-check Step 4. If the pill is hidden behind the menu bar, bump the window level in `lib.rs` (Task 3) from `25` to `101`.

- [ ] **Step 6: Commit**

```bash
git add island/index.html island/src/styles.css island/src/main.js island/src-tauri/capabilities/default.json
git commit -m "Add notch-island frontend UI driven by backend events"
```

---

## Task 6: Final verification and wrap-up

**Files:** none (or optional `island/README.md`)

- [ ] **Step 1: Full clean run-through**

```bash
cd island && pnpm tauri dev
```

Walk the 6 success criteria from Task 5 Step 5 once more, end to end. Fix any that fail before proceeding.

- [ ] **Step 2: Run the Rust test suite**

```bash
cd island/src-tauri && cargo test
```

Expected: the payload test passes; no test failures.

- [ ] **Step 3 (optional): Add a short run note**

If desired, create `island/README.md` documenting `pnpm install` then `pnpm tauri dev`, and the `set_island_state` control point. Commit it.

---

## Self-Review

**Spec coverage:** Every spec success criterion maps to a task — launch/build (T1–T2), top-center + above menu bar + click-through (T3), auto-expand demo + `set_island_state` (T4), pill visuals + verification of all 6 criteria (T5), ⌘Q quit (default Tauri app menu, verified in T5/T6). App-driven expansion (the resolved ambiguity) = `island://state` event from Rust (T4) consumed by frontend (T5). Out-of-scope items (exact notch detection, NSPanel, multi-display) are intentionally excluded.

**Placeholder scan:** No TBD/TODO; every code step contains complete code; every command lists expected output/observation.

**Type consistency:** Event name `island://state`, payload field `state`, and values `"collapsed"`/`"expanded"` are identical across Rust (`IslandState`, both commands, demo driver, unit test) and JS (`event.payload.state`, `dataset.state`, CSS `[data-state=...]`). Command names `set_island_state` / `island_ready` match between `generate_handler!`, the `#[tauri::command]` fns, and the JS `invoke` call. Window label `"main"` matches between `tauri.conf.json` and `get_webview_window("main")`. Window width `360` matches between config and `position_island`'s `win_w`.
