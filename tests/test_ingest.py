"""ingest — turning what lands in inbox/ into traceable, referenceable sources."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from ato_assist import frontmatter, ingest, repo, scaffold, validate
from tests_support import SPEC

SSP = """# System Security Plan

Intro text about the WPS.

## Access control

All privileged access requires MFA. The SIEM records every session.

## Backup

Nightly snapshots.
"""


@pytest.fixture
def assessment(tmp_path: Path) -> Path:
    scaffold.create(tmp_path, SPEC)
    return tmp_path


def drop(root: Path, name: str, text: str = SSP) -> Path:
    path = root / "inbox" / name
    path.write_text(text)
    return path


def docx(root: Path, name: str, paragraphs: list[str]) -> Path:
    """A minimal but real .docx, so the fallback path is exercised without pandoc."""
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    document = (
        '<?xml version="1.0"?><w:document '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    path = root / "inbox" / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)
    return path


def test_an_empty_inbox_reports_nothing_to_do(assessment: Path) -> None:
    report = ingest.run(assessment)
    assert report.ingested == []
    assert report.skipped == []


def test_a_markdown_document_becomes_a_source_directory(assessment: Path) -> None:
    drop(assessment, "ssp-v2.4.md")
    report = ingest.run(assessment)
    assert report.ingested == ["SRC-0001"]
    assert (assessment / "sources" / "SRC-0001-ssp-v2-4" / "index.md").is_file()


def test_the_source_index_passes_the_contract(assessment: Path) -> None:
    drop(assessment, "ssp-v2.4.md")
    ingest.run(assessment)
    index = assessment / "sources" / "SRC-0001-ssp-v2-4" / "index.md"
    relative = repo.relative(assessment, index)
    assert validate.validate_document(relative, index.read_text()) == []


def test_the_index_records_the_hash_and_the_original(assessment: Path) -> None:
    drop(assessment, "ssp-v2.4.md")
    ingest.run(assessment)
    index = assessment / "sources" / "SRC-0001-ssp-v2-4" / "index.md"
    front, _ = frontmatter.parse(index.read_text())
    assert str(front["hash"]).startswith("sha256:")
    assert front["artifact"] == ["inbox/ssp-v2.4.md"]


def test_the_document_is_split_on_headings(assessment: Path) -> None:
    drop(assessment, "ssp-v2.4.md")
    ingest.run(assessment)
    chunks = sorted(
        p.name for p in (assessment / "sources" / "SRC-0001-ssp-v2-4").glob("*.md")
        if p.name != "index.md"
    )
    assert chunks == ["01-system-security-plan.md", "02-access-control.md", "03-backup.md"]


def test_a_chunk_keeps_its_heading_so_the_anchor_resolves(assessment: Path) -> None:
    drop(assessment, "ssp-v2.4.md")
    ingest.run(assessment)
    chunk = assessment / "sources" / "SRC-0001-ssp-v2-4" / "02-access-control.md"
    assert chunk.read_text().startswith("## Access control")


def test_undefined_acronyms_are_queued_not_asked_about(assessment: Path) -> None:
    drop(assessment, "ssp-v2.4.md")
    report = ingest.run(assessment)
    queue = (assessment / "glossary" / "unresolved.md").read_text()
    assert "| SIEM |" in queue
    assert "| WPS |" in queue
    assert report.queued_terms >= 2


def test_terms_the_baseline_glossary_defines_are_not_queued(assessment: Path) -> None:
    drop(assessment, "ssp-v2.4.md", "The SSP describes the ATO scope and the SIEM.")
    ingest.run(assessment)
    queue = (assessment / "glossary" / "unresolved.md").read_text()
    assert "| SIEM |" in queue
    assert "| SSP |" not in queue


def test_the_same_file_dropped_again_is_skipped_not_duplicated(assessment: Path) -> None:
    drop(assessment, "ssp-v2.4.md")
    ingest.run(assessment)
    drop(assessment, "ssp-v2.4.md")
    report = ingest.run(assessment)
    assert report.ingested == []
    assert report.skipped == ["ssp-v2.4.md"]
    assert len(list((assessment / "sources").glob("SRC-*"))) == 1


def test_a_revised_document_supersedes_the_earlier_one(assessment: Path) -> None:
    drop(assessment, "ssp-v2.4.md")
    ingest.run(assessment)
    drop(assessment, "ssp-v2.4.md", SSP + "\n## Logging\n\nNew section.\n")
    report = ingest.run(assessment)
    assert report.ingested == ["SRC-0002"]
    superseded, _ = frontmatter.parse(
        (assessment / "sources" / "SRC-0001-ssp-v2-4" / "index.md").read_text()
    )
    assert superseded["state"] == "superseded"
    revision, _ = frontmatter.parse(
        (assessment / "sources" / "SRC-0002-ssp-v2-4" / "index.md").read_text()
    )
    assert revision["supersedes"] == ["SRC-0001"]


def test_a_revision_reports_what_changed(assessment: Path) -> None:
    drop(assessment, "ssp-v2.4.md")
    ingest.run(assessment)
    drop(assessment, "ssp-v2.4.md", SSP.replace("Nightly snapshots.", "Hourly snapshots."))
    report = ingest.run(assessment)
    assert report.changes == {"SRC-0002": {"added": 0, "changed": 1, "removed": 0}}


@pytest.fixture
def without_pandoc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the no-converter path regardless of what this machine has installed."""
    monkeypatch.setattr("ato_assist.ingest.shutil.which", lambda name: None)


@pytest.mark.usefixtures("without_pandoc")
def test_a_docx_is_read_without_pandoc_and_labelled_ad_hoc(assessment: Path) -> None:
    docx(assessment, "policy.docx", ["Access policy", "The VPC is isolated."])
    ingest.run(assessment)
    index = assessment / "sources" / "SRC-0001-policy" / "index.md"
    front, _ = frontmatter.parse(index.read_text())
    assert front["method"] == "ad-hoc"
    assert "VPC is isolated" in (index.parent / "01-access-policy.md").read_text()


@pytest.mark.usefixtures("without_pandoc")
def test_handling_something_ad_hoc_logs_a_tooling_gap(assessment: Path) -> None:
    docx(assessment, "policy.docx", ["Access policy"])
    ingest.run(assessment)
    assert "docx" in (assessment / "tooling-gaps.md").read_text()


@pytest.mark.usefixtures("without_pandoc")
def test_a_pdf_with_no_extractor_available_produces_a_stub(assessment: Path) -> None:
    (assessment / "inbox" / "policy.pdf").write_bytes(b"%PDF-1.4 not really")
    report = ingest.run(assessment)
    assert "pdftotext" in (assessment / "tooling-gaps.md").read_text()
    assert report.questions


def test_an_unreadable_binary_produces_a_stub_and_a_question(assessment: Path) -> None:
    (assessment / "inbox" / "diagram.vsdx").write_bytes(b"\x00\x01\x02binary")
    report = ingest.run(assessment)
    assert report.ingested == ["SRC-0001"]
    index = assessment / "sources" / "SRC-0001-diagram" / "index.md"
    assert "**Not extracted.**" in index.read_text()
    assert "could not be extracted" in (index.parent / "01-diagram.md").read_text()
    assert report.questions
    assert "diagram.vsdx" in report.questions[0]


def test_the_original_stays_where_it_was_dropped(assessment: Path) -> None:
    original = drop(assessment, "ssp-v2.4.md")
    ingest.run(assessment)
    assert original.is_file()


def test_the_readme_in_the_inbox_is_not_a_document(assessment: Path) -> None:
    assert ingest.run(assessment).ingested == []


def test_ingest_outside_an_assessment_raises(tmp_path: Path) -> None:
    with pytest.raises(ingest.IngestError):
        ingest.run(tmp_path)
