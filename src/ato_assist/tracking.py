"""The phase marker and the request-for-information register.

Both are places where the workbench holds state on the assessor's behalf, and both have
the same rule: the mechanics are automatic, the judgement is not. Moving the phase is an
assertion by the assessor, and an RFI closes because something landed in `sources/`.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

from . import frontmatter
from .repo import ASSESSMENT_FILE, load_assessment, load_yaml

__all__ = ["TrackingError", "close_rfi", "export_rfis", "next_phase", "open_rfi", "set_phase"]


class TrackingError(RuntimeError):
    """The assessment cannot be moved or amended as asked."""


# --- phases -------------------------------------------------------------------------


def phases(root: Path) -> list[str]:
    process = load_yaml(root / "process.yaml") or {}
    return [
        str(phase["id"])
        for phase in process.get("phases") or []
        if isinstance(phase, dict) and phase.get("id")
    ]


def next_phase(root: Path, today: datetime.date | None = None) -> tuple[str, str]:
    """Move to the phase after the current one. Returns (from, to)."""
    order = phases(root)
    current = _current_phase(root)
    if current not in order:
        raise TrackingError(f"the current phase {current!r} is not in process.yaml")
    if order.index(current) + 1 >= len(order):
        raise TrackingError(f"{current!r} is the last phase in process.yaml")
    return set_phase(root, order[order.index(current) + 1], today)


def set_phase(
    root: Path, phase: str, today: datetime.date | None = None
) -> tuple[str, str]:
    """Move the marker to a named phase, recording the move in `decisions.md`."""
    order = phases(root)
    if phase not in order:
        raise TrackingError(f"{phase!r} is not a phase in process.yaml ({', '.join(order)})")
    current = _current_phase(root)
    assessment = load_assessment(root)
    if assessment is None:
        raise TrackingError("assessment.yaml is unreadable")
    assessment["phase"] = phase
    (root / ASSESSMENT_FILE).write_text(frontmatter.dump(assessment), encoding="utf-8")
    _record_decision(
        root,
        f"Phase {current} -> {phase}",
        "Asserted by the assessor.",
        today or datetime.date.today(),
    )
    return current, phase


def _current_phase(root: Path) -> str:
    assessment = load_assessment(root) or {}
    return str(assessment.get("phase", ""))


def _record_decision(root: Path, title: str, why: str, today: datetime.date) -> None:
    path = root / "decisions.md"
    existing = path.read_text(encoding="utf-8") if path.is_file() else "# Decisions\n"
    path.write_text(f"{existing.rstrip()}\n\n## {today.isoformat()} — {title}\n\n{why}\n")


# --- requests for information -------------------------------------------------------


def open_rfi(
    root: Path,
    question: str,
    asked_of: str,
    resolves: list[str] | None = None,
    due: datetime.date | None = None,
    today: datetime.date | None = None,
) -> str:
    """Register a question, and return its ID."""
    today = today or datetime.date.today()
    identifier = _next_rfi_id(root)
    data: dict[str, Any] = {
        "id": identifier,
        "title": _title(question),
        "question": question,
        "asked_of": asked_of,
        "asked_on": today,
        "state": "open",
        "updated": today,
    }
    if due:
        data["due"] = due
    if resolves:
        data["resolves"] = list(resolves)
    body = (
        "Raised because the assessment cannot proceed on this point without an answer.\n"
        "It closes when the answer lands in `sources/` — not when someone says it in a "
        "meeting.\n"
    )
    path = root / "rfi" / f"{identifier}-{_slug(question)}.md"
    path.write_text(frontmatter.render(data, body), encoding="utf-8")
    return identifier


def close_rfi(
    root: Path, identifier: str, source: str, today: datetime.date | None = None
) -> Path:
    """Close a question with the source that answered it."""
    matches = sorted((root / "rfi").glob(f"{identifier}-*.md"))
    if not matches:
        raise TrackingError(f"{identifier} is not in rfi/")
    path = matches[0]
    data, body = frontmatter.parse(path.read_text(encoding="utf-8"))
    today = today or datetime.date.today()
    data["state"] = "answered"
    data["answered_on"] = today
    data["answer_source"] = [{"ref": source}]
    data["updated"] = today
    path.write_text(frontmatter.render(data, body), encoding="utf-8")
    return path


def open_rfis(root: Path) -> list[dict[str, Any]]:
    entries = []
    for path in sorted((root / "rfi").glob("RFI-*.md")):
        try:
            data, _ = frontmatter.parse(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("state") in ("open", "blocked"):
            entries.append(data)
    return entries


def export_rfis(root: Path, today: datetime.date | None = None) -> str:
    """The message the assessor sends, ready to paste, with the marking on it."""
    assessment = load_assessment(root) or {}
    system = assessment.get("system") or {}
    classification = assessment.get("classification") or {}
    name = system.get("name", "the system") if isinstance(system, dict) else "the system"
    marking = classification.get("marking", "UNMARKED") if isinstance(classification, dict) else "?"
    today = today or datetime.date.today()

    entries = open_rfis(root)
    if not entries:
        return f"[{marking}]\n\nNo requests for information are open for {name}.\n"

    lines = [
        f"[{marking}]",
        "",
        f"Subject: {name} — security assessment: request for information",
        "",
        f"As part of the security assessment of {name}, we need the following to proceed.",
        "Where a document already covers a point, a pointer to it is enough.",
        "",
    ]
    for data in entries:
        age = _age(data.get("asked_on"), today)
        lines.append(f"{data['id']}. {data['question']}")
        lines.append(f"    Asked of: {data.get('asked_of', '')}    Open {age} days")
        if data.get("due"):
            lines.append(f"    Needed by: {data['due']}")
        lines.append("")
    lines.append("Please reply with the documents attached rather than in the body, so they")
    lines.append("can be recorded against the assessment.")
    return "\n".join(lines) + "\n"


def _age(asked: Any, today: datetime.date) -> int:
    return (today - asked).days if isinstance(asked, datetime.date) else 0


def _next_rfi_id(root: Path) -> str:
    numbers = [
        int(match.group(1))
        for path in (root / "rfi").glob("RFI-*.md")
        if (match := re.match(r"RFI-(\d{4})", path.name))
    ]
    return f"RFI-{max(numbers, default=0) + 1:04d}"


def _title(question: str) -> str:
    return question.rstrip("?.").strip()[:80]


def _slug(text: str) -> str:
    words = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-").split("-")
    return "-".join(words[:3]) or "question"
