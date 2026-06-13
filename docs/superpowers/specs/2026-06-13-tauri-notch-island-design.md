# Tauri "Notch Island" placeholder (macOS) — Design

**Date:** 2026-06-13
**Status:** Approved
**Scope:** Demo / proof-of-concept

## Summary

A Tauri v2 macOS app that renders a Dynamic-Island-style black pill hugging the
MacBook camera notch. The island has two states — **collapsed** (a pill) and
**expanded** (a larger rounded panel) — and transitions are **driven
programmatically by the backend** ("when the app wants it to"), not by user
hover or click.

Macs have no real Dynamic Island (it is iPhone hardware); this recreates the
effect with a borderless, transparent, always-on-top window placed over the
notch and raised above the menu bar.

Target hardware confirmed for development: notched 14" MacBook Pro
(3024×1964 Liquid Retina XDR), macOS 26.5.

## Architecture

```
┌──────────────────────────── Tauri app ────────────────────────────┐
│                                                                    │
│  Rust backend (src-tauri/)                                         │
│   • On setup: grab NSWindow → raise level ABOVE the menu bar,      │
│     make it click-through (ignore cursor events), park at top-     │
│     center (x = (screenW - winW)/2, y = 0).                        │
│   • #[command] set_island_state("collapsed"|"expanded")            │
│       → emits a Tauri event the frontend listens for.              │
│   • Demo driver: on launch, scripted sequence auto-expands then    │
│     collapses so the capability is visible with no user action.    │
│                                                                    │
│            │  emits "island://state"  ▲  invokes set_island_state  │
│            ▼                          │                            │
│  Webview frontend (src/  — vanilla HTML/CSS/JS)                    │
│   • Fixed transparent canvas = expanded max bounds.                │
│   • Pill element pinned top-center; CSS transitions animate        │
│     collapsed ⇄ expanded. No native window resize → no jitter.     │
│   • Listens for "island://state", swaps class, renders content.    │
└────────────────────────────────────────────────────────────────────┘
```

### Approach chosen

**Approach A (lean):** a single Tauri window plus a small piece of native Rust
(objc2/cocoa) to raise the window above the menu bar. Frontend is plain
HTML/CSS/JS — no framework, no bundler.

Rejected for now — **Approach B:** convert the window to a non-activating
`NSPanel` via a community plugin (over-fullscreen / never-steals-focus). More
moving parts than a placeholder needs; documented as a future upgrade path.

## Window

- One window: borderless (`decorations: false`), transparent
  (`transparent: true`), always-on-top, non-resizable.
- Sized to the **expanded** maximum bounds (≈360×220 logical pt). The window
  never resizes; the pill animates *within* it via CSS. This avoids native
  resize/reposition jitter and re-centering math.
- **Click-through** (`set_ignore_cursor_events(true)`) so it never blocks the
  menu bar or desktop. Because state is app-driven, no user hover/click handling
  is required.
- Raised above the menu bar via native Rust. The exact NSWindow level constant
  and Tauri/objc API will be verified at implementation time, not hardcoded from
  memory.
- Parked at top-center: `x = (monitorWidth - windowWidth) / 2`, `y = 0`
  (accounting for scale factor), using the primary monitor size from Tauri.

## States & content (placeholder)

- **Collapsed:** small pill flush to the screen top — `●  Island` (a colored dot
  + a short label). Top corners square (flush to the screen edge), bottom corners
  rounded, so it blends with the physical notch (both are black).
- **Expanded:** pill grows downward into a rounded panel — title `Placeholder`
  + subtitle `Auto-expanded by the app`.
- Transition animated purely in CSS (width / height / border-radius).

## How the app drives it

- Mechanism: a Tauri `#[command] set_island_state(state)` callable from anywhere
  in the Rust backend; it emits the `island://state` event to the webview.
- Demo: on launch, a scripted sequence calls it
  (collapsed → wait → expanded → wait → collapsed) so the auto-expand is visible
  immediately without user action.

## App lifecycle

- App stays in the Dock; **⌘Q quits** (the borderless window has no close button).
- Menu-bar-only accessory (LSUIElement) behavior is a later refinement.

## Prerequisite

- Install the **Rust toolchain** via `rustup` (Node 25, pnpm 9, and Xcode
  Command Line Tools are already present). Confirm before installing.

## Success criteria

1. `pnpm tauri dev` launches with no errors.
2. A black pill appears hugging the notch, **visible over the menu bar**, at
   top-center.
3. The window is **click-through** (menu bar items at the top remain clickable).
4. The startup sequence **auto-expands then collapses** the island on its own.
5. Calling `set_island_state` flips the state on demand.
6. ⌘Q quits cleanly.

## Out of scope

Exact notch-width detection (a sensible fixed pill width is used instead),
over-fullscreen / non-activating NSPanel behavior, multi-display handling,
persistence, and real (non-placeholder) content or data.
