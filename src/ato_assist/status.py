"""Where the assessment stands, recomputed from the files every time.

Nothing here is stored anywhere. An assessor who has been away for three weeks should be
able to read one screen and know what is blocking the phase, what is unevidenced, and
what is waiting on the customer — without anyone having maintained a status paragraph.
"""

from __future__ import annotations

import datetime
import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Any

from . import checks, oscal, risk
from .repo import RepoIndex, load_yaml

__all__ = ["render", "summary"]

_DECISION = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*[—–-]\s*(.+?)\s*$", re.MULTILINE)
_PLACEHOLDER_FILES = ("process.yaml", "risk-matrix.yaml", "register-columns.yaml")
# The interview records what the assessor could not answer as a checklist. Anything still
# unticked after ingest is the seed list for the first round of RFIs.
_OPEN_QUESTIONS = re.compile(r"^##\s+Open questions\s*$(.*?)(?=^##\s|\Z)", re.M | re.S)
_UNTICKED = re.compile(r"^\s*- \[ \]\s+\S", re.M)
_MAX_RFIS = 4


def summary(root: Path | str, today: datetime.date | None = None) -> dict[str, Any]:
    """The same numbers `render` prints, for anything else that wants them."""
    root = Path(root)
    today = today or datetime.date.today()
    index = RepoIndex(root)
    phase = str(index.assessment.get("phase", "unknown"))
    return {
        "phase": phase,
        "criteria": [result._asdict() for result in checks.evaluate_phase(index, phase, today)],
        "claims": _states(index, "claims"),
        "evidence": _states(index, "evidence"),
        "controls": _states(index, "controls", field="status"),
        "risks": _states(index, "risks"),
        "sources": _states(index, "sources"),
        "unevidenced_claims": _unevidenced(index),
        "open_rfis": _open_rfis(index, today),
        "inbox": _inbox(index),
        "placeholders": _placeholders(root),
        "open_questions": _open_questions(root),
    }


def render(root: Path | str, today: datetime.date | None = None) -> str:
    root = Path(root)
    today = today or datetime.date.today()
    index = RepoIndex(root)
    if not index.assessment:
        return (
            "ATO ASSESSMENT — assessment.yaml is unreadable, so nothing can be derived.\n"
            "Fix the YAML it reports, then run `ato status` again.\n"
        )

    lines = [_headline(index, today), ""]
    lines += _criteria_block(index, today)
    lines += _coverage_block(index, today)
    lines += _rfi_block(index, today)
    lines += _decisions_block(root)
    lines += _footer(root, index, today)
    return "\n".join(line.rstrip() for line in lines).strip() + "\n"


# --- blocks -------------------------------------------------------------------------


def _headline(index: RepoIndex, today: datetime.date) -> str:
    system = index.assessment.get("system") or {}
    classification = index.assessment.get("classification") or {}
    name = system.get("name", "unnamed") if isinstance(system, dict) else "unnamed"
    marking = classification.get("marking", "UNMARKED") if isinstance(classification, dict) else "?"
    data = classification.get("data", "?") if isinstance(classification, dict) else "?"
    phase = index.assessment.get("phase", "unknown")
    results = checks.evaluate_phase(index, str(phase), today)
    met = sum(1 for result in results if result.passed)
    left = f"{name} [{marking}] · {data} data"
    right = f"phase: {phase} ({met}/{len(results)})"
    return f"{left}{' ' * max(1, 98 - len(left) - len(right))}{right}"


def _criteria_block(index: RepoIndex, today: datetime.date) -> list[str]:
    phase = str(index.assessment.get("phase", "unknown"))
    results = checks.evaluate_phase(index, phase, today)
    if not results:
        return [f"No exit criteria defined for phase {phase!r} in process.yaml.", ""]
    lines = [f"EXIT CRITERIA — {phase}"]
    for result in results:
        mark = "x" if result.passed else " "
        lines.append(f"  [{mark}] {result.criterion_id:<28} {result.actual}")
        if not result.passed and result.offenders:
            shown = ", ".join(result.offenders[:2])
            more = f"  (+{len(result.offenders) - 2})" if len(result.offenders) > 2 else ""
            lines.append(f"        {shown}{more}")
    return [*lines, ""]


def _coverage_block(index: RepoIndex, today: datetime.date) -> list[str]:
    _ = today
    lines = ["COVERAGE"]
    controls = _states(index, "controls", field="status")
    if controls:
        assessed = sum(count for state, count in controls.items() if state != "not-assessed")
        total = _framework_total(index) or sum(controls.values())
        percent = f" ({assessed * 100 // total}%)" if total else ""
        lines.append(
            f"  controls   {assessed}/{total} assessed{percent}   " + _tally(controls)
        )
    claims = _states(index, "claims")
    if claims:
        lines.append(f"  claims     {sum(claims.values()):<4} " + _tally(claims))
        flags = _claim_flags(index)
        if flags:
            lines.append(f"             !! {' · '.join(flags)}")
    evidence = _states(index, "evidence")
    if evidence:
        missing = _missing_artifacts(index)
        note = f" · !! {missing} artifacts missing on disk" if missing else ""
        lines.append(f"  evidence   {sum(evidence.values()):<4} " + _tally(evidence) + note)
    sources = _states(index, "sources")
    if sources:
        uncited = _uncited_sources(index)
        note = f" · !! {uncited} never cited by a claim" if uncited else ""
        lines.append(f"  sources    {sum(sources.values()):<4} " + _tally(sources) + note)
    risks = _states(index, "risks")
    if risks:
        severities, unrated = _severities(index)
        note = ("   " + _tally(severities)) if severities else ""
        lines.append(f"  risks      {sum(risks.values()):<4} " + _tally(risks) + note)
        for identifier, problem in unrated:
            lines.append(f"             !! {identifier}: {problem}")
        for path in _accepted_without_rationale(index):
            lines.append(f"             !! {path} accepted with no disposition")
    return [*lines, ""] if len(lines) > 1 else []


def _rfi_block(index: RepoIndex, today: datetime.date) -> list[str]:
    open_rfis = _open_rfis(index, today)
    if not open_rfis:
        return []
    lines = [f"OPEN RFIs ({len(open_rfis)})"]
    for entry in open_rfis[:_MAX_RFIS]:
        overdue = "!" if entry["age"] > 21 else " "
        lines.append(f"  {entry['id']}  {entry['age']:>3}d {overdue} {entry['title'][:60]}")
    if len(open_rfis) > _MAX_RFIS:
        lines.append(f"  (+{len(open_rfis) - _MAX_RFIS} more: ato status --rfi)")
    return [*lines, ""]


def _decisions_block(root: Path) -> list[str]:
    path = root / "decisions.md"
    if not path.is_file():
        return []
    entries = _DECISION.findall(path.read_text(encoding="utf-8"))[-3:]
    if not entries:
        return []
    return ["RECENT DECISIONS", *[f"  {when}  {what[:70]}" for when, what in reversed(entries)], ""]


def _footer(root: Path, index: RepoIndex, today: datetime.date) -> list[str]:
    lines: list[str] = []
    waiting = _inbox(index)
    if waiting:
        plural = "s" if waiting != 1 else ""
        lines.append(f"INBOX  {waiting} file{plural} waiting — run /ato-ingest")
    gaps = _headings(root / "tooling-gaps.md")
    unresolved = _queued_terms(root)
    if gaps or unresolved:
        lines.append(f"GAPS   {gaps} open in tooling-gaps.md    GLOSSARY {unresolved} unresolved")
    questions = _open_questions(root)
    if questions:
        lines.append(
            f"ASK    {questions} unanswered from the interview — raise them as RFIs "
            "if ingest has not answered them"
        )
    for name in _placeholders(root):
        lines.append(f"!      {name} is a placeholder pending team review")
    _ = today
    return lines


# --- counters -----------------------------------------------------------------------


def _framework_total(index: RepoIndex) -> int:
    """How many controls the configured profile actually contains.

    Coverage measured against the files on disk would read 100% the moment the first
    control is written, which is worse than no number at all.
    """
    frameworks = index.assessment.get("frameworks") or []
    if not isinstance(frameworks, list) or not frameworks:
        return 0
    first = frameworks[0]
    if not isinstance(first, dict) or first.get("id") != "ism":
        return 0
    profile = oscal.normalise_profile(first.get("profile"))
    if profile is None:
        return 0
    try:
        return len(oscal.load().profile(profile))
    except oscal.CatalogueError:
        return 0


def _states(index: RepoIndex, kind: str, field: str = "state") -> dict[str, int]:
    counter = Counter(str(item.data.get(field, "?")) for item in index.of_kind(kind))
    return dict(counter)


def _tally(counts: dict[str, int]) -> str:
    return " · ".join(f"{state} {count}" for state, count in sorted(counts.items()))


def _claim_flags(index: RepoIndex) -> list[str]:
    flags = []
    unevidenced = _unevidenced(index)
    if unevidenced:
        plural = "s" if unevidenced != 1 else ""
        flags.append(f"{unevidenced} claim{plural} with no evidence")
    low = sum(1 for item in index.of_kind("claims") if item.data.get("confidence") == "low")
    if low:
        flags.append(f"{low} low confidence")
    ad_hoc = sum(1 for item in index.of_kind("claims") if item.data.get("method") == "ad-hoc")
    if ad_hoc:
        flags.append(f"{ad_hoc} ad-hoc")
    return flags


def _unevidenced(index: RepoIndex) -> int:
    borne = {
        target
        for item in index.of_kind("evidence")
        for target in RepoIndex.refs_of(item, "bears_on")
    }
    return sum(1 for item in index.of_kind("claims") if item.id not in borne)


def _uncited_sources(index: RepoIndex) -> int:
    cited = {
        target for item in index.of_kind("claims") for target in RepoIndex.refs_of(item, "source")
    }
    return sum(1 for item in index.of_kind("sources") if item.id not in cited)


def _missing_artifacts(index: RepoIndex) -> int:
    missing = 0
    for item in index.of_kind("evidence"):
        for artifact in item.data.get("artifact") or []:
            if not (index.root / str(artifact)).exists():
                missing += 1
    return missing


def _severities(index: RepoIndex) -> tuple[dict[str, int], list[tuple[str, str]]]:
    """Risk counts by severity, derived from the matrix, plus anything it could not rate."""
    try:
        rated = risk.rate_all(index.root)
    except risk.MatrixError:
        return {}, []
    counts = Counter(entry.severity for entry in rated if entry.severity)
    unrated = [(entry.id, entry.problem) for entry in rated if entry.severity is None]
    return {str(k): v for k, v in counts.items()}, unrated


def _accepted_without_rationale(index: RepoIndex) -> list[str]:
    return [
        item.id
        for item in index.of_kind("risks")
        if item.data.get("state") == "accepted" and not item.data.get("disposition")
    ]


def _open_rfis(index: RepoIndex, today: datetime.date) -> list[dict[str, Any]]:
    entries = []
    for item in index.of_kind("rfi"):
        if item.data.get("state") not in ("open", "blocked"):
            continue
        asked = item.data.get("asked_on")
        age = (today - asked).days if isinstance(asked, datetime.date) else 0
        entries.append({"id": item.id, "title": str(item.data.get("title", "")), "age": age})
    return sorted(entries, key=lambda entry: -int(entry["age"]))


def _inbox(index: RepoIndex) -> int:
    """Files in `inbox/` that no source has already been made from.

    Under the default retention policy the original stays on disk after ingest, so a
    plain file count would nag forever. The hash is what decides.
    """
    inbox = index.root / "inbox"
    if not inbox.is_dir():
        return 0
    # A file is not waiting if a source was made from it, nor if it was recorded as
    # evidence: the loose-evidence path copies the artefact and leaves the original.
    ingested = {str(item.data.get("hash")) for item in index.of_kind("sources")}
    ingested |= {str(item.data.get("integrity")) for item in index.of_kind("evidence")}
    waiting = 0
    for path in inbox.iterdir():
        if not path.is_file() or path.name == "README.md":
            continue
        if _sha256(path) not in ingested:
            waiting += 1
    return waiting


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(65536), b""):
                digest.update(block)
    except OSError:
        return ""
    return f"sha256:{digest.hexdigest()}"


def _headings(path: Path) -> int:
    if not path.is_file():
        return 0
    return len(_DECISION.findall(path.read_text(encoding="utf-8")))


def _queued_terms(root: Path) -> int:
    path = root / "glossary" / "unresolved.md"
    if not path.is_file():
        return 0
    return len([
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("|") and not line.startswith("|--") and "| Term " not in line
    ])


def _open_questions(root: Path) -> int:
    """Unticked items under `## Open questions` in the interview notes.

    Counted rather than interpreted: whether an ingested document answers a question is a
    judgement someone makes and records by ticking the box. Guessing it from the text
    would be the plugin inventing knowledge.
    """
    path = root / "notes" / "system-context.md"
    if not path.is_file():
        return 0
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    section = _OPEN_QUESTIONS.search(text)
    return len(_UNTICKED.findall(section.group(1))) if section else 0


def _placeholders(root: Path) -> list[str]:
    return [
        name
        for name in _PLACEHOLDER_FILES
        if (load_yaml(root / name) or {}).get("review-required") is True
    ]
