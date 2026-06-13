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

/// How long the pill stays expanded after the last typed message before it
/// collapses again. Debounced: rapid messages keep resetting the timer.
const COLLAPSE_AFTER: Duration = Duration::from_secs(4);

#[derive(Clone, serde::Serialize)]
struct IslandState {
    state: String,
}

type Offsets = Arc<Mutex<HashMap<PathBuf, u64>>>;

/// True only for a message a human literally typed into Claude Code.
///
/// Pure and total: any malformed or non-matching line returns `false`, so the
/// caller never has to reason about parse errors.
pub fn is_typed_user_message(line: &str) -> bool {
    let v: serde_json::Value = match serde_json::from_str(line) {
        Ok(v) => v,
        Err(_) => return false,
    };
    if v.get("type").and_then(|t| t.as_str()) != Some("user") {
        return false;
    }
    if v.get("promptSource").and_then(|s| s.as_str()) != Some("typed") {
        return false;
    }
    if v.get("isSidechain").and_then(|b| b.as_bool()) == Some(true) {
        return false;
    }
    matches!(
        v.get("message").and_then(|m| m.get("content")),
        Some(serde_json::Value::String(s)) if !s.trim().is_empty()
    )
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
                if scan_new_lines(&path, &offsets) {
                    fire(&app, &generation);
                }
            }
        }
    });
}

/// Read newly-appended complete lines from `path` and report whether any is a
/// typed user message. Tracks a per-file byte offset so each line is parsed at
/// most once; only advances past the last complete (newline-terminated) line so
/// a mid-write event never consumes a partial record.
fn scan_new_lines(path: &Path, offsets: &Offsets) -> bool {
    let mut map = offsets.lock().unwrap();
    let start = *map.get(path).unwrap_or(&0);

    let mut file = match File::open(path) {
        Ok(f) => f,
        Err(_) => return false,
    };
    let len = match file.metadata() {
        Ok(m) => m.len(),
        Err(_) => return false,
    };
    if len < start {
        // File was truncated/rotated — reset and wait for the next append.
        map.insert(path.to_path_buf(), len);
        return false;
    }
    if len == start {
        return false;
    }
    if file.seek(SeekFrom::Start(start)).is_err() {
        return false;
    }

    let mut buf = String::new();
    // On a multibyte char split mid-write, read_to_string errors; leave the
    // offset untouched and retry on the next event when the bytes are complete.
    if file.take(len - start).read_to_string(&mut buf).is_err() {
        return false;
    }
    let consumed = match buf.rfind('\n') {
        Some(i) => i + 1,
        None => return false, // no complete line yet
    };
    let hit = buf[..consumed].lines().any(is_typed_user_message);
    map.insert(path.to_path_buf(), start + consumed as u64);
    hit
}

/// Emit `expanded` now and schedule a debounced `collapsed`. Each call bumps a
/// generation counter; only the most recent call's timer is allowed to collapse,
/// so a burst of messages keeps the pill open until 4s after the last one.
fn fire(app: &AppHandle, generation: &Arc<AtomicU64>) {
    let _ = app.emit(
        "island://state",
        IslandState {
            state: "expanded".into(),
        },
    );
    let mine = generation.fetch_add(1, Ordering::SeqCst) + 1;
    let app = app.clone();
    let generation = generation.clone();
    std::thread::spawn(move || {
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

#[cfg(test)]
mod tests {
    use super::is_typed_user_message;

    #[test]
    fn accepts_a_typed_human_prompt() {
        let line = r#"{"type":"user","userType":"external","promptSource":"typed","isSidechain":false,"message":{"role":"user","content":"hello claude"}}"#;
        assert!(is_typed_user_message(line));
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
