"""What a session opens with inside an assessment repository.

Injected by the SessionStart hook. Three jobs: say how the workspace is marked, put the
vocabulary in front of the model before it starts guessing at acronyms, and say what has
changed since last time. Inert everywhere else.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from .repo import find_root_from, load_assessment

__all__ = ["brief"]

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_SESSION_LOG = Path(".ato") / "sessions.jsonl"


def brief(cwd: Path | str, now_iso: str | None = None) -> str:
    """The SessionStart context for the assessment containing ``cwd``, or ``""``."""
    root = find_root_from(cwd)
    if root is None:
        return ""

    now = datetime.datetime.fromisoformat(now_iso) if now_iso else _now()
    previous = _last_session(root)
    _record_session(root, now)

    assessment = load_assessment(root)
    sections = [_headline(assessment), "", _since(previous, now), _inbox(root), ""]
    sections += [_glossary()]
    glossary_path = root / "glossary.md"
    local = glossary_path.read_text(encoding="utf-8") if glossary_path.is_file() else ""
    if local.strip():
        sections += ["", "# Glossary — this assessment", "", local.strip()]
    sections += ["", _unresolved(root)]
    return "\n".join(part for part in sections if part is not None).strip() + "\n"


def _headline(assessment: dict[str, object] | None) -> str:
    if assessment is None:
        return (
            "ATO ASSESSMENT — assessment.yaml is unreadable, so the classification is "
            "unknown. Contract writes are blocked until it parses."
        )
    system = assessment.get("system") or {}
    classification = assessment.get("classification") or {}
    name = system.get("name", "unnamed system") if isinstance(system, dict) else "unnamed system"
    marking = (
        classification.get("marking", "UNMARKED")
        if isinstance(classification, dict)
        else "UNMARKED"
    )
    phase = assessment.get("phase", "unknown")
    return (
        f"ATO ASSESSMENT — {name} [{marking}] — phase: {phase}\n"
        f"Everything written here is {marking}. Every generated output carries that marking."
    )


def _since(previous: datetime.datetime | None, now: datetime.datetime) -> str:
    if previous is None:
        return "This is the first session in this assessment."
    days = (now - previous).days
    return f"Last session {days}d ago." if days else "Last session earlier today."


def _inbox(root: Path) -> str:
    inbox = root / "inbox"
    if not inbox.is_dir():
        return ""
    waiting = [p for p in inbox.iterdir() if p.is_file() and p.name != "README.md"]
    if not waiting:
        return ""
    plural = "s" if len(waiting) != 1 else ""
    return f"{len(waiting)} file{plural} waiting in inbox — run /ato-ingest."


def _glossary() -> str:
    baseline = PLUGIN_ROOT / "config" / "glossary-baseline.md"
    return baseline.read_text(encoding="utf-8").strip() if baseline.is_file() else ""


def _unresolved(root: Path) -> str:
    path = root / "glossary" / "unresolved.md"
    if not path.is_file():
        return ""
    rows = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("|") and not line.startswith("|--") and "| Term " not in line
    ]
    if not rows:
        return ""
    return (
        f"{len(rows)} unresolved glossary terms are queued. Do not guess at a term: add it "
        "to glossary/unresolved.md, mark the item needs-clarification, and carry on."
    )


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _last_session(root: Path) -> datetime.datetime | None:
    log = root / _SESSION_LOG
    try:
        lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        return datetime.datetime.fromisoformat(json.loads(lines[-1])["started"])
    except (OSError, ValueError, KeyError, IndexError):
        return None


def _record_session(root: Path, now: datetime.datetime) -> None:
    log = root / _SESSION_LOG
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"started": now.isoformat()}) + "\n")
    except OSError:
        pass  # session bookkeeping is a convenience, never a blocker
