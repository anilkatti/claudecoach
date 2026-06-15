#!/usr/bin/env bash
#
# Installer for the "Claude Code Coach" daily launchd job (macOS LaunchAgent).
#
# What it does:
#   1. Resolves REPO, python3 and the `claude` CLI.
#   2. Runs ONE coach pass now to validate auth + headless `claude -p` work
#      (and to produce the first ~/.claude/coach/profile.json).
#   3. Only if that smoke pass succeeds, installs + loads the LaunchAgent so
#      the coach runs every day at 09:00.
#
# Idempotent: re-running re-writes the plist and reloads it cleanly.

set -euo pipefail

# --- Resolve this script's directory (handles symlinks, spaces). ------------
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
	DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
	SOURCE="$(readlink "$SOURCE")"
	[ "${SOURCE#/}" = "$SOURCE" ] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"

# --- 1. Resolve REPO, PYTHON, CLAUDE, PATH_FOR_JOB. -------------------------
# REPO = git toplevel of this script's location, falling back to two dirs up
# (install/ -> coach/ -> repo root).
if REPO="$(cd "$SCRIPT_DIR" && git rev-parse --show-toplevel 2>/dev/null)"; then
	:
else
	REPO="$(cd "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"
fi

PLIST_TEMPLATE="$SCRIPT_DIR/com.claudecoach.daily.plist"
if [ ! -f "$PLIST_TEMPLATE" ]; then
	echo "ERROR: plist template not found at: $PLIST_TEMPLATE" >&2
	exit 1
fi

PYTHON="$(command -v python3 || true)"
if [ -z "$PYTHON" ]; then
	echo "ERROR: python3 not found on PATH. Install Python 3 and retry." >&2
	exit 1
fi

CLAUDE="$(command -v claude || true)"
if [ -z "$CLAUDE" ]; then
	echo "ERROR: the 'claude' CLI was not found on PATH." >&2
	echo "       The daily coach job calls Claude headlessly (claude -p) to" >&2
	echo "       generate your profile, so the 'claude' binary must be on PATH." >&2
	echo "       Install the Claude CLI, ensure 'claude' works in this shell," >&2
	echo "       then re-run this installer." >&2
	exit 1
fi
CLAUDE_DIR="$(cd "$(dirname "$CLAUDE")" >/dev/null 2>&1 && pwd)"

# PATH the launchd job will run with: the dir containing `claude` first, then
# the common system/homebrew bins, then whatever PATH this shell has.
PATH_FOR_JOB="$CLAUDE_DIR:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

echo "Claude Code Coach installer"
echo "  repo:    $REPO"
echo "  python:  $PYTHON"
echo "  claude:  $CLAUDE"
echo

# --- 2. Smoke run: validate auth + headless claude, write first profile. ----
echo "Running a first coach pass to validate auth (this calls Claude headlessly)…"
if ! "$PYTHON" "$REPO/coach/scripts/coach_run.py" --once; then
	echo >&2
	echo "ERROR: auth / headless validation FAILED." >&2
	echo "       The daily job was NOT installed." >&2
	echo "       Check that 'claude -p' works in this shell (auth, network)," >&2
	echo "       for example:  echo hi | claude -p" >&2
	echo "       Then re-run this installer." >&2
	exit 1
fi
echo "First coach pass succeeded."
echo

# --- 3. Substitute placeholders -> ~/Library/LaunchAgents, load it. ---------
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_DEST="$LAUNCH_AGENTS_DIR/com.claudecoach.daily.plist"
mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$HOME/.claude/coach"

# Use python3 for substitution so REPO/HOME/PATH values with arbitrary
# characters are inserted verbatim (no sed delimiter/escaping pitfalls).
REPO="$REPO" PYTHON="$PYTHON" HOME_DIR="$HOME" PATH_FOR_JOB="$PATH_FOR_JOB" \
	"$PYTHON" - "$PLIST_TEMPLATE" "$PLIST_DEST" <<'PYEOF'
import os, sys
src, dst = sys.argv[1], sys.argv[2]
with open(src, "r", encoding="utf-8") as f:
    text = f.read()
text = (text
        .replace("__PYTHON__", os.environ["PYTHON"])
        .replace("__REPO__", os.environ["REPO"])
        .replace("__HOME__", os.environ["HOME_DIR"])
        .replace("__PATH__", os.environ["PATH_FOR_JOB"]))
with open(dst, "w", encoding="utf-8") as f:
    f.write(text)
PYEOF

# Reload cleanly (unload errors are fine if it was never loaded).
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

# --- 4. Success block with exact commands. ---------------------------------
cat <<EOF

Installed ✅  — the coach will run daily at 09:00.

  Force a run now:  launchctl start com.claudecoach.daily
  Tail logs:        tail -f ~/.claude/coach/run.log
  Your profile:     ~/.claude/coach/profile.json
  Uninstall:        launchctl unload ~/Library/LaunchAgents/com.claudecoach.daily.plist && rm ~/Library/LaunchAgents/com.claudecoach.daily.plist
  See the badge:    cd island && pnpm tauri dev
EOF
