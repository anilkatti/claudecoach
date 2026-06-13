//! Real-time watcher for "the user just typed a message to Claude Code".
//!
//! Claude Code appends one JSON object per line to
//! `~/.claude/projects/<slug>/<session-id>.jsonl` as each event happens — the
//! file is flushed live, not at session end. We tail those files and flip the
//! island to `expanded` whenever a genuinely *typed* human prompt lands.
//!
//! Discriminator (verified against real transcripts): a typed prompt is the
//! only `type:"user"` entry with `promptSource:"typed"`. Tool results and
//! hook/command injections are also `type:"user"` but carry
//! `promptSource:null` and an array content, so they are ignored.

use std::collections::HashMap;
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::time::Duration;

use notify::{EventKind, RecursiveMode, Watcher};
use tauri::{AppHandle, Emitter};

/// How long the notch stays expanded after the last typed message before it
/// collapses. Debounced: rapid messages keep resetting the timer. Long enough
/// to finish the ~4s typing animation and leave the nudge readable.
const COLLAPSE_AFTER: Duration = Duration::from_secs(9);

#[derive(Clone, serde::Serialize)]
struct IslandState {
    state: String,
}

/// Payload for `island://review` — the one-line coaching nudge the expanded
/// notch types out for the message that was just sent.
#[derive(Clone, serde::Serialize)]
struct Nudge {
    nudge: String,
}

type Offsets = Arc<Mutex<HashMap<PathBuf, u64>>>;

/// The text of a message a human literally typed into Claude Code, or `None`.
///
/// Pure and total: any malformed or non-matching line returns `None`, so the
/// caller never has to reason about parse errors. The discriminator is the same
/// one verified against real transcripts (see module docs): `type:"user"` +
/// `promptSource:"typed"`, not a sidechain, with a non-empty string content.
pub fn typed_user_message(line: &str) -> Option<String> {
    let v: serde_json::Value = serde_json::from_str(line).ok()?;
    if v.get("type").and_then(|t| t.as_str()) != Some("user") {
        return None;
    }
    if v.get("promptSource").and_then(|s| s.as_str()) != Some("typed") {
        return None;
    }
    if v.get("isSidechain").and_then(|b| b.as_bool()) == Some(true) {
        return None;
    }
    match v.get("message").and_then(|m| m.get("content")) {
        Some(serde_json::Value::String(s)) if !s.trim().is_empty() => Some(s.clone()),
        _ => None,
    }
}

/// True iff `line` is a typed human message. Thin wrapper over
/// [`typed_user_message`].
pub fn is_typed_user_message(line: &str) -> bool {
    typed_user_message(line).is_some()
}

/// Start watching `~/.claude/projects` for typed user messages. Returns
/// immediately; all work happens on a background thread. A no-op if the home
/// directory or projects directory can't be found.
pub fn start(app: AppHandle) {
    let base = match dirs::home_dir() {
        Some(home) => home.join(".claude").join("projects"),
        None => return,
    };
    if !base.is_dir() {
        return;
    }

    // Seed offsets with current file sizes so we never replay session history —
    // only messages typed *after* the app starts should light up the island.
    let offsets: Offsets = Arc::new(Mutex::new(HashMap::new()));
    {
        let mut map = offsets.lock().unwrap();
        for path in jsonl_files(&base) {
            if let Ok(meta) = std::fs::metadata(&path) {
                map.insert(path, meta.len());
            }
        }
    }

    let generation = Arc::new(AtomicU64::new(0));

    std::thread::spawn(move || {
        let (tx, rx) = mpsc::channel();
        let mut watcher = match notify::recommended_watcher(tx) {
            Ok(w) => w,
            Err(_) => return,
        };
        if watcher.watch(&base, RecursiveMode::Recursive).is_err() {
            return;
        }
        // `watcher` must stay alive for the lifetime of this loop; the blocking
        // `for` over `rx` keeps it in scope.
        for res in rx {
            let event = match res {
                Ok(e) => e,
                Err(_) => continue,
            };
            if !matches!(event.kind, EventKind::Modify(_) | EventKind::Create(_)) {
                continue;
            }
            for path in event.paths {
                if path.extension().and_then(|e| e.to_str()) != Some("jsonl") {
                    continue;
                }
                if let Some(message) = scan_new_lines(&path, &offsets) {
                    fire(&app, &generation, message);
                }
            }
        }
    });
}

/// Read newly-appended complete lines from `path` and return the text of the
/// most recent typed user message among them, if any. Tracks a per-file byte
/// offset so each line is parsed at most once; only advances past the last
/// complete (newline-terminated) line so a mid-write event never consumes a
/// partial record.
fn scan_new_lines(path: &Path, offsets: &Offsets) -> Option<String> {
    let mut map = offsets.lock().unwrap();
    let start = *map.get(path).unwrap_or(&0);

    let mut file = File::open(path).ok()?;
    let len = file.metadata().ok()?.len();
    if len < start {
        // File was truncated/rotated — reset and wait for the next append.
        map.insert(path.to_path_buf(), len);
        return None;
    }
    if len == start {
        return None;
    }
    file.seek(SeekFrom::Start(start)).ok()?;

    let mut buf = String::new();
    // On a multibyte char split mid-write, read_to_string errors; leave the
    // offset untouched and retry on the next event when the bytes are complete.
    if file.take(len - start).read_to_string(&mut buf).is_err() {
        return None;
    }
    let consumed = match buf.rfind('\n') {
        Some(i) => i + 1,
        None => return None, // no complete line yet
    };
    map.insert(path.to_path_buf(), start + consumed as u64);
    // Most recent typed message in this batch (usually exactly one).
    buf[..consumed].lines().rev().find_map(typed_user_message)
}

/// Review a freshly-typed `message`, then reveal the notch with the nudge.
///
/// The review (a `claude -p` round-trip) is kicked off *immediately* on a
/// background thread, but the notch stays collapsed until the response comes
/// back — then it expands, types the nudge, and collapses after
/// [`COLLAPSE_AFTER`]. A generation counter makes the latest message win: if
/// another message arrives mid-review, this call stops emitting (no stale pop,
/// no stale nudge, no early collapse).
fn fire(app: &AppHandle, generation: &Arc<AtomicU64>, message: String) {
    let mine = generation.fetch_add(1, Ordering::SeqCst) + 1;
    let app = app.clone();
    let generation = generation.clone();
    std::thread::spawn(move || {
        // Fire the review now; this blocks this thread for a second or two.
        let nudge = reviewer::review(&message).unwrap_or_else(|| reviewer::fallback(mine));
        if generation.load(Ordering::SeqCst) != mine {
            return; // a newer message superseded us mid-review
        }
        // Response is back — now open the notch and let the expand animation
        // play before the nudge types in.
        let _ = app.emit(
            "island://state",
            IslandState {
                state: "expanded".into(),
            },
        );
        std::thread::sleep(Duration::from_millis(450));
        if generation.load(Ordering::SeqCst) != mine {
            return;
        }
        let _ = app.emit("island://review", Nudge { nudge });
        std::thread::sleep(COLLAPSE_AFTER);
        if generation.load(Ordering::SeqCst) == mine {
            let _ = app.emit(
                "island://state",
                IslandState {
                    state: "collapsed".into(),
                },
            );
        }
    });
}

/// Recursively collect every `*.jsonl` file under `base`.
fn jsonl_files(base: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    let entries = match std::fs::read_dir(base) {
        Ok(e) => e,
        Err(_) => return out,
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            out.extend(jsonl_files(&path));
        } else if path.extension().and_then(|e| e.to_str()) == Some("jsonl") {
            out.push(path);
        }
    }
    out
}

/// Per-message coaching review. Shells out to `coach/scripts/review_message.py`
/// (which routes the model call through `coach_llm` — the one model call site),
/// reads back its `{ "nudge": ... }` JSON, and returns the nudge text.
mod reviewer {
    use std::io::Write;
    use std::path::{Path, PathBuf};
    use std::process::{Command, Stdio};

    /// Generic, non-fabricated lines shown when the review can't run (e.g.
    /// `claude`/`python3` not on PATH). Indexed by the message's generation so
    /// consecutive failures don't repeat the same line.
    const FALLBACKS: [&str; 3] = [
        "On it — keep the momentum going.",
        "Noted. Keep your asks clear and you'll move fast.",
        "Got it — steer, check, ship.",
    ];

    pub fn fallback(generation: u64) -> String {
        FALLBACKS[(generation as usize) % FALLBACKS.len()].to_string()
    }

    /// Review `message`, returning the nudge text, or `None` if anything fails.
    pub fn review(message: &str) -> Option<String> {
        let script = locate_script()?;
        let mut child = Command::new("python3")
            .arg(&script)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .ok()?;

        // Write the message to stdin, then drop the handle to signal EOF so the
        // script's `sys.stdin.read()` returns.
        {
            let mut stdin = child.stdin.take()?;
            stdin.write_all(message.as_bytes()).ok()?;
        }

        let out = child.wait_with_output().ok()?;
        if !out.status.success() {
            return None;
        }
        let v: serde_json::Value = serde_json::from_slice(&out.stdout).ok()?;
        let nudge = v.get("nudge").and_then(|n| n.as_str())?.trim();
        if nudge.is_empty() {
            None
        } else {
            Some(nudge.to_string())
        }
    }

    /// Find `coach/scripts/review_message.py`: honor `CLAUDECOACH_REPO`, else
    /// walk up from the current directory looking for the repo layout.
    fn locate_script() -> Option<PathBuf> {
        const REL: &str = "coach/scripts/review_message.py";
        if let Ok(repo) = std::env::var("CLAUDECOACH_REPO") {
            let p = Path::new(&repo).join(REL);
            if p.is_file() {
                return Some(p);
            }
        }
        let mut dir = std::env::current_dir().ok()?;
        loop {
            let candidate = dir.join(REL);
            if candidate.is_file() {
                return Some(candidate);
            }
            if !dir.pop() {
                return None;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{is_typed_user_message, typed_user_message};

    #[test]
    fn accepts_a_typed_human_prompt() {
        let line = r#"{"type":"user","userType":"external","promptSource":"typed","isSidechain":false,"message":{"role":"user","content":"hello claude"}}"#;
        assert!(is_typed_user_message(line));
    }

    #[test]
    fn extracts_the_message_text() {
        let line = r#"{"type":"user","promptSource":"typed","message":{"role":"user","content":"fix the flaky test"}}"#;
        assert_eq!(typed_user_message(line).as_deref(), Some("fix the flaky test"));
    }

    #[test]
    fn extraction_returns_none_for_tool_result() {
        let line = r#"{"type":"user","promptSource":null,"message":{"content":[{"type":"tool_result","content":"ok"}]}}"#;
        assert!(typed_user_message(line).is_none());
    }

    #[test]
    fn rejects_tool_result() {
        // promptSource is null and content is an array of tool_result blocks.
        let line = r#"{"type":"user","userType":"external","promptSource":null,"isSidechain":false,"message":{"role":"user","content":[{"type":"tool_result","content":"ok"}]}}"#;
        assert!(!is_typed_user_message(line));
    }

    #[test]
    fn rejects_hook_or_command_injection() {
        // Synthetic user entry: promptSource null, content array of text blocks.
        let line = r#"{"type":"user","userType":"external","promptSource":null,"message":{"role":"user","content":[{"type":"text","text":"injected context"}]}}"#;
        assert!(!is_typed_user_message(line));
    }

    #[test]
    fn rejects_assistant_and_meta() {
        assert!(!is_typed_user_message(r#"{"type":"assistant","message":{"content":"hi"}}"#));
        assert!(!is_typed_user_message(r#"{"type":"summary"}"#));
    }

    #[test]
    fn rejects_sidechain_subagent_prompt() {
        let line = r#"{"type":"user","promptSource":"typed","isSidechain":true,"message":{"content":"subagent task"}}"#;
        assert!(!is_typed_user_message(line));
    }

    #[test]
    fn rejects_empty_or_whitespace_content() {
        let line = r#"{"type":"user","promptSource":"typed","message":{"content":"   "}}"#;
        assert!(!is_typed_user_message(line));
    }

    #[test]
    fn rejects_malformed_json() {
        assert!(!is_typed_user_message("not json"));
        assert!(!is_typed_user_message(""));
    }
}
