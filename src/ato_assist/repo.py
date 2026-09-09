"""Locating an assessment repository and reading its two configuration files.

Root discovery walks up from the *file being written*, never from the process working
directory: subagents, worktrees and background shells all have an unreliable cwd, and a
hook that trusted it would either miss writes or fire outside the assessment entirely.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path, PurePosixPath
from typing import Any

from . import frontmatter
from .miniyaml import MiniYamlError, loads
from .schema import SCHEMAS
from .validate import schema_for_path

__all__ = [
    "ASSESSMENT_FILE",
    "Item",
    "RepoIndex",
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


@dataclasses.dataclass(frozen=True)
class Item:
    """One contract file, parsed once."""

    id: str
    kind: str
    path: str  # repo-relative POSIX
    data: dict[str, Any]


class RepoIndex:
    """Every contract file in an assessment, read in one pass.

    Built once and handed to the checks and to status, so a repo-wide sweep costs one
    walk rather than one per question asked.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.assessment = load_assessment(self.root) or {}
        self.items: dict[str, Item] = {}
        self._by_kind: dict[str, list[Item]] = {kind: [] for kind in SCHEMAS}
        for path in sorted(self.root.rglob("*.md")):
            item = self._read(path)
            if item is not None:
                self.items[item.id] = item
                self._by_kind[item.kind].append(item)

    def _read(self, path: Path) -> Item | None:
        try:
            relative_path = path.relative_to(self.root).as_posix()
        except ValueError:
            return None
        resolved = schema_for_path(relative_path)
        if resolved is None:
            return None
        try:
            data, _ = frontmatter.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            return None
        identifier = data.get("id")
        if not isinstance(identifier, str):
            return None
        return Item(identifier, resolved[0].directory, relative_path, data)

    def of_kind(self, kind: str) -> list[Item]:
        return self._by_kind.get(kind, [])

    @staticmethod
    def refs_of(item: Item, field: str) -> list[str]:
        """The IDs a field points at, with any anchor stripped."""
        value = item.data.get(field) or []
        if not isinstance(value, list):
            return []
        targets: list[str] = []
        for entry in value:
            ref = entry.get("ref") if isinstance(entry, dict) else entry
            if isinstance(ref, str):
                targets.append(ref.split("#", 1)[0])
        return targets

    def short_name(self) -> str:
        system = self.assessment.get("system")
        if not isinstance(system, dict):
            return "assessment"
        return str(system.get("short_name", "assessment"))

    def process(self) -> dict[str, Any]:
        return load_yaml(self.root / "process.yaml") or {}
