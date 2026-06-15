//! Live "coach profile" badge: reflects the user's overall builder score.
//!
//! The Python coaching engine writes `~/.claude/coach/profile.json` whenever it
//! recomputes the user's profile. We read that file, distill it to a tiny badge
//! (band + overall score + trend arrow), and push it to the island.
//!
//! Schema (only `band` and `overall` are required; the rest is ignored or
//! optional):
//! ```json
//! {"updated_at": "...", "overall": 7.1, "band": "Solid",
//!  "axes": {...}, "strongest_axis": {...}, "weakest_axis": {...},
//!  "trend": {"overall_delta": 0.4, "note": null},
//!  "n_sessions": 142, "n_episodes": 38, "disclaimer": "..."}
//! ```

use std::path::Path;
use std::sync::mpsc;

use notify::{EventKind, RecursiveMode, Watcher};
use tauri::{AppHandle, Emitter};

/// Compact badge derived from the full profile. `trend` is "up"/"down"/"flat".
#[derive(Clone, serde::Serialize)]
pub struct ProfileBadge {
    pub band: String,
    pub overall: f64,
    pub trend: String,
}

/// Distill `~/.claude/coach/profile.json` into a [`ProfileBadge`].
///
/// Pure and total like `watcher::is_typed_user_message`: any malformed JSON or
/// missing required field (`band` as a non-empty string, `overall` as a number)
/// returns `None`. `trend.overall_delta` is optional — a missing/null delta maps
/// to "flat".
pub fn parse_profile(json: &str) -> Option<ProfileBadge> {
    let v: serde_json::Value = serde_json::from_str(json).ok()?;

    let band = v.get("band").and_then(|b| b.as_str())?;
    if band.trim().is_empty() {
        return None;
    }

    let overall = v.get("overall").and_then(|o| o.as_f64())?;

    let delta = v
        .get("trend")
        .and_then(|t| t.get("overall_delta"))
        .and_then(|d| d.as_f64());
    let trend = match delta {
        Some(d) if d > 0.0 => "up",
        Some(d) if d < 0.0 => "down",
        _ => "flat",
    };

    Some(ProfileBadge {
        band: band.to_string(),
        overall,
        trend: trend.to_string(),
    })
}

/// Start watching `~/.claude/coach/profile.json` for changes. Returns
/// immediately; all work happens on a background thread. A no-op if the home
/// directory can't be found. If the file already exists it is read and emitted
/// once, immediately.
pub fn start(app: AppHandle) {
    let home = match dirs::home_dir() {
        Some(h) => h,
        None => return,
    };
    let coach_dir = home.join(".claude").join("coach");
    let profile_path = coach_dir.join("profile.json");

    // Emit the current profile right away if it's already on disk.
    read_and_emit(&app, &profile_path);

    std::thread::spawn(move || {
        // Watch whichever ancestor exists so we still catch the file being
        // created later: prefer the coach dir, fall back to ~/.claude.
        let claude_dir = home.join(".claude");
        let watch_dir = if coach_dir.is_dir() {
            coach_dir.clone()
        } else if claude_dir.is_dir() {
            claude_dir
        } else {
            return;
        };

        let (tx, rx) = mpsc::channel();
        let mut watcher = match notify::recommended_watcher(tx) {
            Ok(w) => w,
            Err(_) => return,
        };
        if watcher.watch(&watch_dir, RecursiveMode::Recursive).is_err() {
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
            if event.paths.iter().any(|p| p == &profile_path) {
                read_and_emit(&app, &profile_path);
            }
        }
    });
}

/// Read `path`, parse it, and emit `island://profile` if it yields a badge.
fn read_and_emit(app: &AppHandle, path: &Path) {
    let json = match std::fs::read_to_string(path) {
        Ok(s) => s,
        Err(_) => return,
    };
    if let Some(badge) = parse_profile(&json) {
        let _ = app.emit("island://profile", badge);
    }
}

#[cfg(test)]
mod tests {
    use super::parse_profile;

    const FULL: &str = r#"{
        "updated_at": "2026-06-13T00:00:00Z",
        "overall": 7.1,
        "band": "Solid",
        "axes": {"execution": 7.0},
        "strongest_axis": {"name": "execution", "score": 8.0},
        "weakest_axis": {"name": "planning", "score": 6.0},
        "trend": {"overall_delta": 0.4, "note": null},
        "n_sessions": 142,
        "n_episodes": 38,
        "disclaimer": "self-assessment"
    }"#;

    #[test]
    fn accepts_a_full_valid_profile() {
        let badge = parse_profile(FULL).expect("valid profile parses");
        assert_eq!(badge.band, "Solid");
        assert_eq!(badge.overall, 7.1);
        assert_eq!(badge.trend, "up");
    }

    #[test]
    fn rejects_malformed_json() {
        assert!(parse_profile("not json").is_none());
        assert!(parse_profile("").is_none());
    }

    #[test]
    fn rejects_missing_band() {
        let line = r#"{"overall": 7.1, "trend": {"overall_delta": 0.4}}"#;
        assert!(parse_profile(line).is_none());
    }

    #[test]
    fn rejects_empty_band() {
        let line = r#"{"band": "   ", "overall": 7.1}"#;
        assert!(parse_profile(line).is_none());
    }

    #[test]
    fn rejects_missing_overall() {
        let line = r#"{"band": "Solid", "trend": {"overall_delta": 0.4}}"#;
        assert!(parse_profile(line).is_none());
    }

    #[test]
    fn maps_positive_delta_to_up() {
        let line = r#"{"band": "Solid", "overall": 7.1, "trend": {"overall_delta": 0.4}}"#;
        assert_eq!(parse_profile(line).unwrap().trend, "up");
    }

    #[test]
    fn maps_negative_delta_to_down() {
        let line = r#"{"band": "Solid", "overall": 7.1, "trend": {"overall_delta": -0.4}}"#;
        assert_eq!(parse_profile(line).unwrap().trend, "down");
    }

    #[test]
    fn maps_null_or_missing_delta_to_flat() {
        let null_delta = r#"{"band": "Solid", "overall": 7.1, "trend": {"overall_delta": null}}"#;
        assert_eq!(parse_profile(null_delta).unwrap().trend, "flat");

        let no_trend = r#"{"band": "Solid", "overall": 7.1}"#;
        assert_eq!(parse_profile(no_trend).unwrap().trend, "flat");

        let zero_delta = r#"{"band": "Solid", "overall": 7.1, "trend": {"overall_delta": 0.0}}"#;
        assert_eq!(parse_profile(zero_delta).unwrap().trend, "flat");
    }
}
