#!/bin/sh
# Point this clone's git hooks at the tracked hooks in scripts/hooks/.
# Run once per clone (the setting is local, not committed). Idempotent.
#
# Why per clone: git hooks and core.hooksPath are never pushed, so every machine
# you push from needs this once — otherwise a push from an un-installed clone
# ships payload changes without a version bump (the exact confusion this fixes).
set -eu
repo_root=$(git rev-parse --show-toplevel)
git -C "$repo_root" config core.hooksPath "$repo_root/scripts/hooks"
chmod +x "$repo_root/scripts/hooks/pre-push"
echo "claudecoach: git hooks installed (core.hooksPath -> $repo_root/scripts/hooks)."
