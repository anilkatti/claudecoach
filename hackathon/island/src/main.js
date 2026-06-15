// Vanilla template (no bundler) — use the global Tauri API.
const { listen } = window.__TAURI__.event;
const { invoke } = window.__TAURI__.core;

const island = document.getElementById("island");
const typedEl = document.getElementById("typed");
const cursor = document.getElementById("cursor");
const coachBadge = document.getElementById("coach-badge");

const TREND_ARROW = { up: "▲", down: "▼", flat: "·" };

// ---- build the Claude burst logo (12 rotated spokes) ----
(function buildLogo() {
  const g = document.getElementById("spokes");
  const base = g.querySelector("rect");
  const N = 12;
  for (let i = 1; i < N; i++) {
    const r = base.cloneNode(true);
    r.setAttribute("transform", `rotate(${(360 / N) * i} 50 50)`);
    g.appendChild(r);
  }
})();

let typingTimer = null;

function type(text) {
  clearTimeout(typingTimer);
  typedEl.textContent = "";
  cursor.style.display = "inline-block";
  let i = 0;
  (function step() {
    if (i <= text.length) {
      typedEl.textContent = text.slice(0, i);
      i++;
      // slight human jitter in typing speed
      const delay = 24 + Math.random() * 45;
      typingTimer = setTimeout(step, delay);
    }
  })();
}

function applyState(state) {
  if (state !== "collapsed" && state !== "expanded") return;
  island.dataset.state = state;
  // On expand the notch opens with a blinking cursor ("thinking") and waits for
  // the backend review (island://review) to type the coaching nudge.
  clearTimeout(typingTimer);
  typedEl.textContent = "";
}

async function init() {
  await listen("island://state", (event) => {
    applyState(event.payload?.state);
  });

  // Per-message coaching nudge: typed into the expanded notch once the backend
  // review of the just-sent message returns (see src-tauri/src/watcher.rs).
  await listen("island://review", (event) => {
    const nudge = event.payload?.nudge;
    if (typeof nudge === "string" && nudge) type(nudge);
  });

  await listen("island://profile", (event) => {
    const p = event.payload;
    if (!p || typeof p.overall !== "number" || !p.band) {
      coachBadge.hidden = true;
      return;
    }
    const trend = p.trend in TREND_ARROW ? p.trend : "flat";
    coachBadge.innerHTML =
      `${p.band} · ${p.overall.toFixed(1)} ` +
      `<span class="arrow-${trend}">${TREND_ARROW[trend]}</span>`;
    coachBadge.hidden = false;
  });
  // Listener is ready — let the backend drive the demo expand/collapse.
  await invoke("island_ready");
}

init();
