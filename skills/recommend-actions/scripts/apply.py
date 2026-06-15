#!/usr/bin/env python3
"""Reversible file primitives for the /recommend-actions apply loop. There is
deliberately NO destructive delete: "remove a capability" means archive (move),
which is recoverable. Config edits back up and write atomically; archive/restore
never overwrite an existing target."""

import argparse
import difflib
import os
import shutil
import sys


def _nonclobber_path(path):
    """Return `path` if free, else `path.1`, `path.2`, … — never an existing path."""
    candidate, n = path, 0
    while os.path.exists(candidate):
        n += 1
        candidate = f"{path}.{n}"
    return candidate


def backup_file(path):
    """Copy `path` to `path.bak` (or .bak.1, .bak.2, …); return the backup path."""
    dest = _nonclobber_path(path + ".bak")
    shutil.copy2(path, dest)
    return dest


def compute_diff(old_text, new_text, path):
    """Unified diff (string) of old → new for display before applying."""
    return "".join(difflib.unified_diff(
        old_text.splitlines(keepends=True), new_text.splitlines(keepends=True),
        fromfile=f"a/{path}", tofile=f"b/{path}"))


def apply_edit(path, new_text):
    """Back up (if present) then atomically overwrite `path`. Returns {path, backed_up_to}."""
    backup = backup_file(path) if os.path.exists(path) else None
    tmp = _nonclobber_path(path + ".tmp")
    with open(tmp, "w") as f:
        f.write(new_text)
    os.replace(tmp, path)  # atomic on the same filesystem
    return {"path": path, "backed_up_to": backup}


def archive_capability(path, archive_dir):
    """Move a capability (file/dir/symlink) into archive_dir without overwriting an
    existing archived entry of the same name. Reversible. Returns the archive dest."""
    os.makedirs(archive_dir, exist_ok=True)
    dest = _nonclobber_path(os.path.join(archive_dir, os.path.basename(path.rstrip("/"))))
    shutil.move(path, dest)
    return dest


def restore_capability(archived_path, original_path):
    """Move an archived capability back, without overwriting anything now at the
    original path. Returns the actual restored location."""
    dest = _nonclobber_path(original_path)
    os.makedirs(os.path.dirname(dest.rstrip("/")) or ".", exist_ok=True)
    shutil.move(archived_path, dest)
    return dest


def _read(path):
    with open(path) as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser(description="Reversible apply primitives.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diff"); d.add_argument("path"); d.add_argument("new_file")
    e = sub.add_parser("edit"); e.add_argument("path"); e.add_argument("new_file")
    a = sub.add_parser("archive"); a.add_argument("path"); a.add_argument("archive_dir")
    r = sub.add_parser("restore"); r.add_argument("archived_path"); r.add_argument("original_path")
    args = ap.parse_args()

    if args.cmd == "diff":
        old = _read(args.path) if os.path.exists(args.path) else ""
        sys.stdout.write(compute_diff(old, _read(args.new_file), args.path))
    elif args.cmd == "edit":
        print(apply_edit(args.path, _read(args.new_file)))
    elif args.cmd == "archive":
        print(archive_capability(args.path, args.archive_dir))
    elif args.cmd == "restore":
        print(restore_capability(args.archived_path, args.original_path))


if __name__ == "__main__":
    main()
