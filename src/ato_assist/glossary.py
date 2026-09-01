"""Finding terms nobody has defined yet.

An undefined acronym must never stop the work and must never be guessed at. Ingest scans
what it reads, subtracts everything already defined, and queues the rest with a count and
a sample sentence so `/ato-glossary` can walk them one at a time later. Questions are
batched; they are never asked per term.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

__all__ = ["Term", "defined_terms", "merge_queue", "record", "scan", "unresolved"]

# Three to six capitals with optional trailing digits: ISM, MFA, SIEM, ISM2. Longer runs
# are almost always a shouted word; two-letter pairs are mostly noise (OS, IT, AU), and a
# genuine one an assessor cares about will be caught when they read the extraction.
_ACRONYM = re.compile(r"\b[A-Z]{3,6}\d*\b")
_SENTENCE = re.compile(r"[^.!?\n]*[.!?]|[^.!?\n]+")
_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*([^|]*?)\s*\|\s*(.*?)\s*\|$")

_TABLE_HEADER = (
    "| Term | Count | First seen | Sample |\n"
    "|------|-------|-----------|--------|\n"
)


class Term(NamedTuple):
    term: str
    sightings: int  # not `count`: NamedTuple inherits tuple.count and would shadow it
    sample: str
    first_seen: str = ""


def defined_terms(glossary_text: str) -> set[str]:
    """Terms a glossary defines. A heading is ``## TERM`` or ``## TERM — expansion``."""
    terms: set[str] = set()
    for heading in _HEADING.findall(glossary_text):
        terms.add(re.split(r"\s+[—–-]\s+", heading, maxsplit=1)[0].strip())
    return terms


def scan(text: str) -> dict[str, Term]:
    """Every acronym in ``text``, with how often it appears and where it first appears."""
    found: dict[str, Term] = {}
    for sentence in (match.group(0).strip() for match in _SENTENCE.finditer(text)):
        if _is_shouted(sentence):
            continue
        for acronym in _ACRONYM.findall(sentence):
            existing = found.get(acronym)
            found[acronym] = Term(
                acronym,
                (existing.sightings if existing else 0) + 1,
                existing.sample if existing else sentence,
            )
    return found


def _is_shouted(sentence: str) -> bool:
    """A line that is all capitals is a heading or emphasis, not a run of acronyms."""
    letters = [character for character in sentence if character.isalpha()]
    words = [word for word in sentence.split() if any(c.isalpha() for c in word)]
    return bool(letters) and all(c.isupper() for c in letters) and len(words) > 2


def unresolved(text: str, defined: set[str]) -> dict[str, Term]:
    return {term: found for term, found in scan(text).items() if term not in defined}


def merge_queue(existing: str, found: dict[str, Term], source_id: str) -> str:
    """Fold newly seen terms into the queue, keeping the first sighting of each."""
    rows: dict[str, Term] = {}
    for line in existing.splitlines():
        match = _ROW.match(line.strip())
        if match and match.group(1) != "Term":
            rows[match.group(1)] = Term(
                match.group(1), int(match.group(2)), match.group(4), match.group(3)
            )
    for term, entry in found.items():
        previous = rows.get(term)
        rows[term] = Term(
            term,
            (previous.sightings if previous else 0) + entry.sightings,
            previous.sample if previous else _cell(entry.sample),
            previous.first_seen if previous else source_id,
        )
    lines = [
        f"| {row.term} | {row.sightings} | {row.first_seen} | {row.sample} |"
        for row in sorted(rows.values(), key=lambda r: (-r.sightings, r.term))
    ]
    return _TABLE_HEADER + "\n".join(lines) + ("\n" if lines else "")


def record(root: Path, text: str, source_id: str, defined: set[str]) -> int:
    """Queue whatever ``text`` uses and nobody has defined. Returns how many are new."""
    queue = Path(root) / "glossary" / "unresolved.md"
    found = unresolved(text, defined)
    if not found:
        return 0
    existing = queue.read_text(encoding="utf-8") if queue.is_file() else ""
    preamble, _, _ = existing.partition("| Term ")
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.write_text(preamble + merge_queue(existing, found, source_id), encoding="utf-8")
    return len(found)


def _cell(text: str) -> str:
    """One line, pipes escaped, short enough to scan in a table."""
    text = " ".join(text.split()).replace("|", "\\|")
    return text if len(text) <= 80 else text[:79] + "…"
