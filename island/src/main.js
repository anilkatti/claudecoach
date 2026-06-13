// Vanilla template (no bundler) — use the global Tauri API.
const { listen } = window.__TAURI__.event;
const { invoke } = window.__TAURI__.core;

const island = document.getElementById("island");
const typedEl = document.getElementById("typed");
const cursor = document.getElementById("cursor");

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

const messages = [
  "You've been heads-down for 90 minutes. Stand up, roll your shoulders, look at something far away.",
  "That bug you're stuck on? Step away for 5. Your brain solves it in the shower, not the stack trace.",
  "Nice commit. Momentum is real — ride it into the next one while you're warm.",
  "Hydrate. You've shipped three PRs and zero glasses of water today.",
  "Big meeting in 10. Close the extra tabs, breathe, you've got the context.",
];
let msgIndex = 0;
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
  if (state === "expanded") {
    // wait for expand + header animation before typing
    setTimeout(() => type(messages[msgIndex]), 480);
    msgIndex = (msgIndex + 1) % messages.length;
  } else {
    clearTimeout(typingTimer);
    typedEl.textContent = "";
  }
}

async function init() {
  await listen("island://state", (event) => {
    applyState(event.payload?.state);
  });
  // Listener is ready — let the backend drive the demo expand/collapse.
  await invoke("island_ready");
}

init();
