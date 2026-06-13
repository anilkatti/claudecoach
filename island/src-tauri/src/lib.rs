mod watcher;

use tauri::{AppHandle, Emitter, Manager};

#[derive(Clone, serde::Serialize)]
struct IslandState {
    state: String,
}

/// Programmatic control point: any backend code can flip the island state.
#[tauri::command]
fn set_island_state(app: AppHandle, state: String) {
    let _ = app.emit("island://state", IslandState { state });
}

/// The frontend calls this once it has registered its listener. We then start
/// the transcript watcher, which expands the island whenever the user types a
/// message to Claude Code (see `watcher`).
#[tauri::command]
fn island_ready(app: AppHandle) {
    watcher::start(app);
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![set_island_state, island_ready])
        .setup(|app| {
            let window = app.get_webview_window("main").expect("main window exists");
            #[cfg(not(target_os = "macos"))]
            {
                position_island(&window);
                let _ = window.set_always_on_top(true);
            }
            let _ = window.set_ignore_cursor_events(true);
            let _ = window.show();
            // On macOS, pin the window to the absolute top of the display (into the
            // notch / menu-bar region) and raise it above the menu bar. Done after
            // show() so the OS doesn't re-constrain the frame back under the menu bar.
            // NOTE: we manage the window *level* ourselves here instead of using
            // Tauri's always-on-top (which pins it to the floating level, below the
            // menu bar) — see position_island_macos.
            #[cfg(target_os = "macos")]
            position_island_macos(&window);
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

/// Park the window at the top-center of the primary display, flush to the top edge.
/// Used on non-macOS platforms; macOS uses `position_island_macos` instead.
#[cfg(not(target_os = "macos"))]
fn position_island(window: &tauri::WebviewWindow) {
    if let Ok(Some(monitor)) = window.primary_monitor() {
        let scale = monitor.scale_factor();
        let screen = monitor.size().to_logical::<f64>(scale);
        let win_w = 600.0_f64; // keep in sync with width in tauri.conf.json
        let x = (screen.width - win_w) / 2.0;
        let _ = window.set_position(tauri::LogicalPosition::new(x, 0.0));
    }
}

/// Pin the window to the very top of the display, centered, so the rendered pill
/// overlaps the hardware notch — and raise it above the macOS menu bar.
///
/// Tauri/tao's `set_position` constrains a window to the screen's *visible* frame
/// (i.e. below the menu bar / notch), which leaves the pill dangling under the real
/// notch. Setting the `NSWindow` frame origin directly against the screen's *full*
/// frame bypasses that constraint — borderless windows are not re-constrained on
/// `setFrameOrigin:`, so the window lands flush with the physical top edge.
#[cfg(target_os = "macos")]
fn position_island_macos(window: &tauri::WebviewWindow) {
    apply_overlay(window);

    // tao re-asserts the window level on some post-show events, which can knock the
    // pill back below the menu bar. Re-apply shortly after on the main thread.
    let w = window.clone();
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_millis(700));
        let w2 = w.clone();
        let _ = w.run_on_main_thread(move || apply_overlay(&w2));
    });
}

/// Pin the window to the very top of the display, centered, raised above the menu
/// bar so the rendered pill overlaps the hardware notch. Idempotent — safe to re-run.
#[cfg(target_os = "macos")]
fn apply_overlay(window: &tauri::WebviewWindow) {
    use objc2_app_kit::NSWindow;
    use objc2_foundation::NSPoint;

    let Ok(ptr) = window.ns_window() else { return };
    let ns_window = unsafe { &*(ptr as *mut NSWindow) };

    // The menu bar lives at NSMainMenuWindowLevel (24) and on notched Macs the
    // window server keeps it painted over that top strip. Use the screen-saver
    // level (1000) so the pill renders above the menu bar in the notch region.
    let level: objc2_app_kit::NSWindowLevel = 1000;
    ns_window.setLevel(level);

    // `screen()` is the display the window currently sits on. Its `frame` spans the
    // entire display including the notch/menu-bar strip (unlike `visibleFrame`).
    if let Some(screen) = ns_window.screen() {
        let screen_frame = screen.frame();
        let win_frame = ns_window.frame();
        let win_w = win_frame.size.width;
        let win_h = win_frame.size.height;

        // Cocoa coordinates are bottom-left origin with y growing upward, so the
        // window's bottom-left y must be (screen top - window height) to pin its
        // top edge to the top of the display.
        let x = screen_frame.origin.x + (screen_frame.size.width - win_w) / 2.0;
        let y = screen_frame.origin.y + screen_frame.size.height - win_h;
        ns_window.setFrameOrigin(NSPoint::new(x, y));
    }
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
