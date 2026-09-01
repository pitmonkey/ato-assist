"""Turning what lands in `inbox/` into traceable, referenceable sources.

Three rules shape this module:

* A document that comes back revised produces a diff and a superseding source, never a
  duplicate. The hash decides.
* Nothing blocks. If the right tool is not installed, the text is extracted some other
  way, the result is labelled ``method: ad-hoc``, and the gap is logged for later. Only a
  genuinely unreadable file produces a stub and a question.
* Undefined terms are queued, never asked about one at a time.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import re
import shutil
import subprocess
import xml.etree.ElementTree as ElementTree
import zipfile
from pathlib import Path
from typing import Any, NamedTuple

from . import frontmatter, glossary
from .repo import find_root_from
from .session import PLUGIN_ROOT

__all__ = ["IngestError", "Report", "run"]

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$", re.MULTILINE)
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".rst", ".csv", ".json", ".yaml", ".yml"}


class IngestError(RuntimeError):
    """Ingest was asked to run somewhere that is not an assessment."""


@dataclasses.dataclass
class Report:
    """What one ingest run did. Accumulated as it goes, so it is mutable on purpose."""

    ingested: list[str] = dataclasses.field(default_factory=list)
    skipped: list[str] = dataclasses.field(default_factory=list)
    changes: dict[str, dict[str, int]] = dataclasses.field(default_factory=dict)
    queued_terms: int = 0
    questions: list[str] = dataclasses.field(default_factory=list)
    gaps: list[str] = dataclasses.field(default_factory=list)


class _Extraction(NamedTuple):
    text: str
    method: str
    gap: str = ""
    question: str = ""


def run(root: Path | str, today: datetime.date | None = None) -> Report:
    """Ingest every new document in ``inbox/``."""
    root = Path(root)
    if find_root_from(root) != root:
        raise IngestError(f"{root} is not an assessment root (no assessment.yaml)")
    today = today or datetime.date.today()

    known = _known_sources(root)
    defined = _defined_terms(root)
    report = Report()

    for original in sorted((root / "inbox").iterdir()):
        if not original.is_file() or original.name == "README.md":
            continue
        digest = _sha256(original)
        if digest in {source["hash"] for source in known.values()}:
            report.skipped.append(original.name)
            continue

        extraction = _extract(original)
        source_id = _next_source_id(root)
        previous = _previous_revision(known, original.name)
        directory = root / "sources" / f"{source_id}-{_slug(original.stem)}"
        directory.mkdir(parents=True)

        chunks = _write_chunks(directory, extraction.text)
        _write_index(directory, source_id, original, digest, extraction, previous, today)
        if previous:
            _mark_superseded(root, known, previous, today)
            report.changes[source_id] = _diff(root, known[previous]["directory"], chunks)

        report.queued_terms += glossary.record(root, extraction.text, source_id, defined)
        if extraction.gap:
            _log_gap(root, extraction.gap, today)
            report.gaps.append(extraction.gap)
        if extraction.question:
            report.questions.append(extraction.question)
        report.ingested.append(source_id)
        known[source_id] = {
            "hash": digest,
            "artifact": original.name,
            "directory": directory,
        }
    return report


# --- reading what was dropped -------------------------------------------------------


def _extract(path: Path) -> _Extraction:
    suffix = path.suffix.lower()
    if suffix in _TEXT_SUFFIXES:
        try:
            return _Extraction(path.read_text(encoding="utf-8"), "document-review")
        except UnicodeDecodeError:
            pass
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix == ".pdf":
        return _extract_pdf(path)
    return _stub(path, f"{suffix or 'this file type'} is not text and cannot be extracted")


def _extract_docx(path: Path) -> _Extraction:
    converted = _pandoc(path)
    if converted is not None:
        return _Extraction(converted, "document-review")
    try:
        with zipfile.ZipFile(path) as archive:
            document = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile):
        return _stub(path, "the .docx could not be opened")
    paragraphs = [
        "".join(node.itertext()).strip()
        for node in ElementTree.fromstring(document).iter(f"{_WORD_NS}p")
    ]
    text = _as_markdown([p for p in paragraphs if p])
    return _Extraction(
        text,
        "ad-hoc",
        gap="docx conversion without pandoc — paragraphs are recovered from the XML, so "
            "tables, lists and heading levels are lost. Install pandoc, or write an adapter.",
    )


def _extract_pdf(path: Path) -> _Extraction:
    if shutil.which("pdftotext"):
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True
        )
        if result.returncode == 0:
            return _Extraction(result.stdout, "document-review")
    return _stub(
        path,
        "no PDF text extractor is available",
        gap="PDF extraction needs pdftotext (poppler-utils); it is not installed.",
    )


def _pandoc(path: Path) -> str | None:
    if not shutil.which("pandoc"):
        return None
    result = subprocess.run(
        ["pandoc", "-t", "markdown", str(path)], capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else None


def _stub(path: Path, why: str, gap: str = "") -> _Extraction:
    """A file nobody can read still gets a source, so the gap is visible and citable."""
    return _Extraction(
        f"# {path.stem}\n\nThe content of `{path.name}` could not be extracted: {why}.\n\n"
        "Nothing in this source can be cited until someone supplies a readable version or "
        "transcribes it.\n",
        "ad-hoc",
        gap=gap,
        question=f"{path.name} could not be read ({why}). Can the owner supply it in "
                 "another format, or should it be transcribed by hand?",
    )


def _as_markdown(paragraphs: list[str]) -> str:
    """Treat a short paragraph with no terminator as a heading; it usually is one."""
    lines: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) < 80 and not paragraph.endswith((".", ":", ";", ",")):
            lines.append(f"## {paragraph}")
        else:
            lines.append(paragraph)
    return "\n\n".join(lines) + "\n"


# --- writing the source -------------------------------------------------------------


def _write_chunks(directory: Path, text: str) -> dict[str, str]:
    """Split on headings, one file per section, keeping the heading so anchors resolve."""
    matches = list(_HEADING.finditer(text))
    sections: list[tuple[str, str]] = []
    if not matches or matches[0].start() > 0:
        preamble = text[: matches[0].start()] if matches else text
        if preamble.strip():
            sections.append(("Preamble", preamble.strip() + "\n"))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(2), text[match.start() : end].strip() + "\n"))

    written: dict[str, str] = {}
    for number, (title, body) in enumerate(sections, start=1):
        name = f"{number:02d}-{_slug(title)}.md"
        (directory / name).write_text(body, encoding="utf-8")
        written[name] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return written


def _write_index(
    directory: Path,
    source_id: str,
    original: Path,
    digest: str,
    extraction: _Extraction,
    previous: str | None,
    today: datetime.date,
) -> None:
    data: dict[str, Any] = {
        "id": source_id,
        "title": original.stem.replace("-", " ").replace("_", " "),
        "kind": "document",
        "received": datetime.date.fromtimestamp(original.stat().st_mtime),
        "origin": "inbox",
        "classification": "UNOFFICIAL",
        "hash": digest,
        "artifact": [f"inbox/{original.name}"],
        "method": extraction.method,
        "state": "ingested",
        "updated": today,
    }
    if previous:
        data["supersedes"] = [previous]
    body = (
        f"Ingested from `inbox/{original.name}`.\n\n"
        "Sections are split by heading into the files beside this one; an anchor in a "
        "reference matches a heading in one of them.\n\n"
        "## Assessor note\n\n"
        "`classification` is UNOFFICIAL until someone sets it. Correct it before citing "
        "this source.\n"
    )
    if extraction.question:
        # An unreadable file still gets a source, so the hole in the record is visible
        # from the index rather than only from a chunk nobody opens.
        body += f"\n**Not extracted.** {extraction.question}\n"
    elif extraction.method == "ad-hoc":
        body += (
            "\nThis document was handled ad hoc — see `tooling-gaps.md`. Treat anything "
            "extracted from it with lower confidence.\n"
        )
    (directory / "index.md").write_text(frontmatter.render(data, body), encoding="utf-8")


def _mark_superseded(
    root: Path, known: dict[str, dict[str, Any]], source_id: str, today: datetime.date
) -> None:
    index = known[source_id]["directory"] / "index.md"
    data, body = frontmatter.parse(index.read_text(encoding="utf-8"))
    data["state"] = "superseded"
    data["updated"] = today
    index.write_text(frontmatter.render(data, body), encoding="utf-8")
    _ = root


def _diff(root: Path, previous: Path, chunks: dict[str, str]) -> dict[str, int]:
    """How the revision differs from what it supersedes, by section."""
    before = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in previous.glob("*.md")
        if path.name != "index.md"
    }
    _ = root
    return {
        "added": len([name for name in chunks if name not in before]),
        "changed": len([n for n, h in chunks.items() if n in before and before[n] != h]),
        "removed": len([name for name in before if name not in chunks]),
    }


# --- bookkeeping --------------------------------------------------------------------


def _known_sources(root: Path) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for index in sorted((root / "sources").glob("SRC-*/index.md")):
        try:
            data, _ = frontmatter.parse(index.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        artifacts = data.get("artifact") or []
        sources[str(data.get("id"))] = {
            "hash": data.get("hash"),
            "artifact": Path(str(artifacts[0])).name if artifacts else "",
            "state": data.get("state"),
            "directory": index.parent,
        }
    return sources


def _previous_revision(known: dict[str, dict[str, Any]], filename: str) -> str | None:
    matches = [
        source_id
        for source_id, source in known.items()
        if source["artifact"] == filename and source["state"] != "superseded"
    ]
    return max(matches) if matches else None


def _next_source_id(root: Path) -> str:
    existing = [
        int(match.group(1))
        for path in (root / "sources").glob("SRC-*")
        if (match := re.match(r"SRC-(\d{4})", path.name))
    ]
    return f"SRC-{max(existing, default=0) + 1:04d}"


def _defined_terms(root: Path) -> set[str]:
    baseline = PLUGIN_ROOT / "config" / "glossary-baseline.md"
    text = baseline.read_text(encoding="utf-8") if baseline.is_file() else ""
    local = root / "glossary.md"
    if local.is_file():
        text += "\n" + local.read_text(encoding="utf-8")
    return glossary.defined_terms(text)


def _log_gap(root: Path, gap: str, today: datetime.date) -> None:
    log = root / "tooling-gaps.md"
    existing = log.read_text(encoding="utf-8") if log.is_file() else "# Tooling gaps\n"
    if gap in existing:
        return
    with log.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {today.isoformat()} — {gap.split('—')[0].strip()}\n\n{gap}\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"

