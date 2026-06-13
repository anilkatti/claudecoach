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
