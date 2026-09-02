"""The commits the workbench makes on the assessor's behalf.

One assessment, one repository, and a log that reads as the assessment's history rather
than as a pile of file saves. Commits happen at named steps — ingest, an RFI changing
state, a phase moving — not on every write, which is why this is called from the CLI and
not from a hook.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = ["KINDS", "GitError", "commit"]

# A closed set, so `git log --oneline` stays scannable as a record of what happened.
KINDS = {
    "init": "the assessment was created",
    "ingest": "documents became sources",
    "extract": "sources became claims",
    "map": "claims were mapped onto controls",
    "evidence": "evidence was reconciled against claims",
    "risk": "a risk was raised or changed",
    "rfi": "a request for information changed state",
    "phase": "the phase marker moved",
    "export": "outputs were regenerated",
    "note": "assessor notes or decisions",
}


class GitError(RuntimeError):
    """Git refused, or was asked for something that would spoil the log."""


def commit(root: Path | str, kind: str, summary: str, detail: str = "") -> bool:
    """Stage everything and commit. Returns False when there was nothing to commit."""
    if kind not in KINDS:
        known = ", ".join(sorted(KINDS))
        raise GitError(f"{kind!r} is not an assessment step; use one of: {known}")
    root = Path(root)
    if not (root / ".git").is_dir():
        raise GitError(f"{root} is not a git repository")

    _git(root, "add", "-A")
    if not _run(root, "diff", "--cached", "--quiet").returncode:
        return False
    message = f"{kind}: {summary}" + (f"\n\n{detail}\n" if detail else "\n")
    _git(root, "commit", "-q", "-m", message)
    return True


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    except OSError as exc:
        raise GitError(f"git is not available: {exc}") from exc


def _git(root: Path, *args: str) -> None:
    result = _run(root, *args)
    if result.returncode:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
