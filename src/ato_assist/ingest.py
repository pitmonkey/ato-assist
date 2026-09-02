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
from .repo import find_root_from, load_assessment
from .session import PLUGIN_ROOT

__all__ = ["IngestError", "Report", "run"]

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$", re.MULTILINE)
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".rst", ".csv", ".json", ".yaml", ".yml"}
# Suffix -> the binary that preserves structure, and what is lost without it.
_CONVERTERS = {
    ".docx": ("pandoc", "headings, tables and lists are lost"),
    ".pdf": ("pdftotext", "nothing can be read from the file at all"),
}
# Below this, a "successful" conversion has produced one undifferentiated blob.
_MIN_SECTIONS = 2
_PART_WORDS = 1200
# Above this, a document with no headings is a conversion failure rather than a note.
_SUBSTANTIAL = 20_000


class IngestError(RuntimeError):
    """Ingest was asked to run somewhere that is not an assessment."""


class ConverterMissing(IngestError):
    """A queued document needs a converter that is not installed.

    Losing formatting is a note-and-continue. Losing document structure is not: an SSP
    whose sections are gone cannot support claim extraction, because there is no section
    for a claim to cite. That is a stop, before anything lands on disk.
    """


@dataclasses.dataclass
class Report:
    """What one ingest run did. Accumulated as it goes, so it is mutable on purpose."""

    ingested: list[str] = dataclasses.field(default_factory=list)
    skipped: list[str] = dataclasses.field(default_factory=list)
    changes: dict[str, dict[str, int]] = dataclasses.field(default_factory=dict)
    queued_terms: int = 0
    questions: list[str] = dataclasses.field(default_factory=list)
    gaps: list[str] = dataclasses.field(default_factory=list)
    sections: dict[str, int] = dataclasses.field(default_factory=dict)
    unusable: dict[str, str] = dataclasses.field(default_factory=dict)
    frameworks_seen: dict[str, list[str]] = dataclasses.field(default_factory=dict)


class _Extraction(NamedTuple):
    text: str
    method: str
    gap: str = ""
    question: str = ""


def run(
    root: Path | str,
    today: datetime.date | None = None,
    *,
    force: bool = False,
    reingest: str | None = None,
) -> Report:
    """Ingest every new document in ``inbox/``.

    ``force`` accepts a conversion that will lose structure. ``reingest`` discards a
    source and reads its original again, which is the supported way to redo a bad
    conversion — hand-deleting a source directory leaves the glossary queue and the gap
    log describing a document that no longer exists.
    """
    root = Path(root)
    if find_root_from(root) != root:
        raise IngestError(f"{root} is not an assessment root (no assessment.yaml)")
    today = today or datetime.date.today()

    if reingest:
        _discard(root, reingest)
    _preflight(root, force)

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

        chunks, structured = _write_chunks(directory, extraction.text)
        report.sections[source_id] = len(chunks)
        unusable = _judge_extraction(directory, chunks, structured)
        if unusable:
            report.unusable[source_id] = unusable
            extraction = extraction._replace(method="ad-hoc")
            _log_gap(root, f"{original.name} — {unusable}", today)
            report.gaps.append(f"{original.name} — {unusable}")
        seen = _frameworks_in(extraction.text, _configured_frameworks(root))
        if seen:
            report.frameworks_seen[source_id] = seen
        _write_index(
            directory, source_id, original, digest, extraction, previous, today,
            anchors_unavailable=not structured,
        )
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
    """Paragraphs, as paragraphs.

    An earlier version promoted any short paragraph without terminal punctuation to a
    heading, on the theory that it usually is one. On a control table every cell
    qualifies — "Responsible Role", "Not Applicable", a person's name — and each became a
    section with no body. Worse than the noise: a fabricated heading becomes a real
    anchor, so a claim could cite a section that never existed in the document. Structure
    that is not in the source does not get invented here.
    """
    return "\n\n".join(paragraphs) + "\n"


# --- writing the source -------------------------------------------------------------


def _write_chunks(directory: Path, text: str) -> tuple[dict[str, str], bool]:
    """Split the extraction into files. Returns the chunks and whether they are sections.

    A document with headings splits on them, and a reference can then cite a section by
    anchor. A document with none — which is what Word produces when the author used bold
    and bigger instead of styles — is split by size into parts instead. Parts are honest:
    they carry no anchor anybody could cite, and the source says so.
    """
    matches = list(_HEADING.finditer(text))
    if len(matches) < _MIN_SECTIONS:
        return _write_parts(directory, text), False

    sections: list[tuple[str, str]] = []
    if matches[0].start() > 0 and text[: matches[0].start()].strip():
        sections.append(("Preamble", text[: matches[0].start()].strip() + "\n"))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(2), text[match.start() : end].strip() + "\n"))

    # Pad to the width of the count: two-wide numbering puts 100- before 09-, which
    # loses document order at the filesystem layer for anything over 99 sections.
    width = max(2, len(str(len(sections))))
    written: dict[str, str] = {}
    for number, (title, body) in enumerate(sections, start=1):
        written[f"{number:0{width}d}-{_slug(title)}.md"] = _write_chunk(
            directory, f"{number:0{width}d}-{_slug(title)}.md", body
        )
    return written, True


def _write_parts(directory: Path, text: str) -> dict[str, str]:
    """Split unstructured text into readable parts on a paragraph boundary."""
    parts: list[str] = []
    current: list[str] = []
    words = 0
    for paragraph in text.split("\n\n"):
        current.append(paragraph)
        words += len(paragraph.split())
        if words >= _PART_WORDS:
            parts.append("\n\n".join(current).strip() + "\n")
            current, words = [], 0
    if current and "\n\n".join(current).strip():
        parts.append("\n\n".join(current).strip() + "\n")

    width = max(2, len(str(len(parts))))
    return {
        f"part-{number:0{width}d}.md": _write_chunk(
            directory, f"part-{number:0{width}d}.md", body
        )
        for number, body in enumerate(parts or [text], start=1)
    }


def _write_chunk(directory: Path, name: str, body: str) -> str:
    (directory / name).write_text(body, encoding="utf-8")
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _judge_extraction(directory: Path, chunks: dict[str, str], structured: bool) -> str:
    """Say plainly when what landed cannot support claim extraction.

    A converter that fails is forgivable; an ingest that calls the result a success is
    not. Both failure shapes look fine from the outside — one chunk of a megabyte, or
    thousands of chunks holding only a heading — so the outcome is checked rather than
    the converter.
    """
    if not chunks:
        return "nothing was extracted"
    bodies = [_body_length(directory / name) for name in chunks]
    if structured:
        empty = sum(1 for length in bodies if length == 0)
        if empty > len(bodies) // 2:
            return (
                f"{empty} of {len(bodies)} sections hold only a heading; the converter "
                "recovered no document structure worth citing"
            )
    elif sum(bodies) > _SUBSTANTIAL:
        # The dangerous shape: the converter reports success, the text is all there, and
        # there is still nothing a claim can cite. Word produces this whenever the author
        # used bold-and-bigger instead of heading styles, which is most of the time.
        return (
            f"no headings were found in a document of {sum(bodies):,} characters, so it "
            f"is split into {len(chunks)} parts by size and nothing in it can be cited by "
            "section"
        )
    return ""


def _body_length(path: Path) -> int:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return 0
    return sum(len(line.strip()) for line in lines if line.strip() and not line.startswith("#"))


def _write_index(
    directory: Path,
    source_id: str,
    original: Path,
    digest: str,
    extraction: _Extraction,
    previous: str | None,
    today: datetime.date,
    anchors_unavailable: bool = False,
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
    if anchors_unavailable:
        data["anchors_unavailable"] = True
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
    if anchors_unavailable:
        body += (
            "\n**No sections.** The converter found no headings in this document, so it "
            "is split into parts by size. A reference to this source cannot carry an "
            "anchor, and `locator` is the only way to say where something came from.\n"
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



# --- preflight, discarding, and the framework scan -----------------------------------


def _preflight(root: Path, force: bool) -> None:
    """Refuse before writing anything, when a queued document needs a missing converter."""
    if force:
        return
    blocked: list[str] = []
    for path in sorted((root / "inbox").iterdir()):
        if not path.is_file() or path.name == "README.md":
            continue
        converter = _CONVERTERS.get(path.suffix.lower())
        if converter and not shutil.which(converter[0]):
            blocked.append(f"{path.name} needs {converter[0]}, which is not installed — "
                           f"without it, {converter[1]}")
    if blocked:
        raise ConverterMissing(
            "\n".join(blocked)
            + "\n\nA document whose structure is gone cannot support claim extraction: "
            "there is no section for a claim to cite. Install the converter and run "
            "again, or re-run with --force to accept a degraded ingest."
        )


def _discard(root: Path, source_id: str) -> None:
    """Remove a source so its original can be read again.

    Also drops the glossary terms it first queued, because a term whose only sighting was
    in a discarded source is describing a document that no longer exists. Terms first seen
    elsewhere keep their counts, which will be slightly high until they are next resolved
    — an acceptable inaccuracy in a backlog, and better than dropping another source's
    work. Gap entries are dated log lines and are left alone.
    """
    directories = list((root / "sources").glob(f"{source_id}-*"))
    if not directories:
        raise IngestError(f"{source_id} is not a source in {root / 'sources'}")
    for directory in directories:
        shutil.rmtree(directory)

    queue = root / "glossary" / "unresolved.md"
    if not queue.is_file():
        return
    kept = [
        line
        for line in queue.read_text(encoding="utf-8").splitlines()
        if not (line.startswith("|") and f"| {source_id} |" in line)
    ]
    queue.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _configured_frameworks(root: Path) -> set[str]:
    assessment = load_assessment(root) or {}
    return {
        str(entry.get("id", "")).lower()
        for entry in assessment.get("frameworks") or []
        if isinstance(entry, dict)
    }


def _frameworks_in(text: str, configured: set[str]) -> list[str]:
    """Frameworks this document names, other than the one the assessment is configured for.

    An SSP written against 800-53 and assessed against the ISM will read as widespread
    non-compliance at control mapping, when in fact it was documented to a different
    catalogue. That is worth knowing at ingest, when it is still cheap.
    """
    lowered = text.lower()
    seen = [
        name
        for name, (pattern, key) in _FRAMEWORK_NAMES.items()
        if key not in configured and re.search(pattern, lowered)
    ]
    return sorted(seen)


# Name -> (pattern, the assessment.yaml framework id it corresponds to, if any).
_FRAMEWORK_NAMES = {
    "NIST SP 800-53": (r"800[\s-]?53", "nist-800-53"),
    "FedRAMP": (r"\bfedramp\b", "fedramp"),
    "ISO 27001": (r"\biso[\s/]?27001\b", "iso-27001"),
    "SOC 2": (r"\bsoc\s?2\b", "soc2"),
    "Essential Eight": (r"\bessential eight\b", "e8"),
    "ISM": (r"\bism\b|information security manual", "ism"),
}
