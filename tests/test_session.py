"""session — what a session opens with inside an assessment repository."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ato_assist import scaffold, session
from tests_support import SPEC  # noqa: E402


@pytest.fixture
def assessment(tmp_path: Path) -> Path:
    scaffold.create(tmp_path, SPEC)
    return tmp_path


def test_says_nothing_outside_an_assessment(tmp_path: Path) -> None:
    assert session.brief(tmp_path) == ""


def test_leads_with_the_marking_and_the_system(assessment: Path) -> None:
    first = session.brief(assessment).splitlines()[0]
    assert "PROTECTED" in first
    assert "Example System" in first


def test_carries_the_baseline_glossary(assessment: Path) -> None:
    assert "Authority to Operate" in session.brief(assessment)


def test_carries_the_assessment_glossary_after_the_baseline(assessment: Path) -> None:
    (assessment / "glossary.md").write_text("# Glossary\n\n## WPS\n\nWidget Processing System.\n")
    brief = session.brief(assessment)
    assert brief.index("Authority to Operate") < brief.index("Widget Processing System")


def test_counts_unresolved_glossary_terms(assessment: Path) -> None:
    (assessment / "glossary" / "unresolved.md").write_text(
        "| Term | Count | First seen | Sample |\n|---|---|---|---|\n"
        "| CAP | 4 | SRC-0001 | ... |\n| SIEM | 2 | SRC-0002 | ... |\n"
    )
    assert "2 unresolved" in session.brief(assessment)


def test_records_the_session_so_the_next_one_knows_how_long_it_has_been(
    assessment: Path,
) -> None:
    session.brief(assessment)
    session.brief(assessment)
    entries = (assessment / ".ato" / "sessions.jsonl").read_text().splitlines()
    assert len(entries) == 2
    assert "started" in json.loads(entries[0])


def test_reports_how_long_since_the_previous_session(assessment: Path) -> None:
    (assessment / ".ato").mkdir(exist_ok=True)
    (assessment / ".ato" / "sessions.jsonl").write_text(
        json.dumps({"started": "2026-08-27T09:00:00+00:00"}) + "\n"
    )
    assert "6d ago" in session.brief(assessment, now_iso="2026-09-02T09:00:00+00:00")


def test_the_first_session_says_so(assessment: Path) -> None:
    assert "first session" in session.brief(assessment)


def test_carries_the_derived_status_rather_than_a_second_account_of_it(
    assessment: Path,
) -> None:
    (assessment / "inbox" / "ssp-v2.4.pdf").write_text("x")
    brief = session.brief(assessment)
    assert "EXIT CRITERIA" in brief
    assert "1 file waiting" in brief


def test_a_broken_assessment_still_produces_a_brief(assessment: Path) -> None:
    (assessment / "assessment.yaml").write_text("classification:\n\tdata: bad\n")
    assert "unreadable" in session.brief(assessment)
