"""Locating an assessment repository and reading its two configuration files.

Root discovery walks up from the *file being written*, never from the process working
directory: subagents, worktrees and background shells all have an unreliable cwd, and a
hook that trusted it would either miss writes or fire outside the assessment entirely.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from .miniyaml import MiniYamlError, loads

__all__ = [
    "ASSESSMENT_FILE",
    "find_root",
    "find_root_from",
    "load_assessment",
    "load_yaml",
    "relative",
]

ASSESSMENT_FILE = "assessment.yaml"
# Deep enough for any real layout, shallow enough that a stray marker far up the tree
# cannot capture unrelated files.
_MAX_DEPTH = 8


def find_root(path: Path | str) -> Path | None:
    """The assessment root above the file ``path``, or ``None`` if there is not one nearby."""
    return find_root_from(Path(path).parent)


def find_root_from(directory: Path | str) -> Path | None:
    """The assessment root at or above ``directory``."""
    current = Path(directory)
    for _ in range(_MAX_DEPTH):
        if (current / ASSESSMENT_FILE).is_file():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


def relative(root: Path, path: Path | str) -> str:
    """``path`` as a repo-rooted POSIX string, which is the form every ref uses."""
    return PurePosixPath(Path(path).resolve().relative_to(Path(root).resolve())).as_posix()


def load_yaml(path: Path) -> dict[str, Any] | None:
    """Parse a YAML file, or ``None`` if it is missing or outside the subset."""
    try:
        return loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, MiniYamlError):
        return None


def load_assessment(root: Path) -> dict[str, Any] | None:
    return load_yaml(Path(root) / ASSESSMENT_FILE)
