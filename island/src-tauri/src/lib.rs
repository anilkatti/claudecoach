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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![set_island_state, island_ready])
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn island_state_serializes_with_state_field() {
        let json = serde_json::to_string(&IslandState { state: "expanded".into() }).unwrap();
        assert_eq!(json, r#"{"state":"expanded"}"#);
    }
}
