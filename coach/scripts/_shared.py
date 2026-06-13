"""Add the repo's shared extraction scripts to sys.path so coach modules can
import condense/events/gitdata/decisions/episodes without copying them."""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SCRIPTS = os.path.join(_REPO, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

REPO_ROOT = _REPO
SHARED_SCRIPTS = _SCRIPTS
