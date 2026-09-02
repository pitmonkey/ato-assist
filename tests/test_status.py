"""status — where the assessment stands, recomputed from the files every time."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from ato_assist import frontmatter, scaffold, status
from tests_support import SPEC

TODAY = datetime.date(2026, 9, 2)


@pytest.fixture
def assessment(tmp_path: Path) -> Path:
    scaffold.create(tmp_path, SPEC)
    return tmp_path


def add(root: Path, relative: str, **fields: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.render(dict(fields), "Body.\n"))


def claim(root: Path, number: int, **overrides: object) -> None:
    fields: dict[str, object] = {
        "id": f"CLM-{number:04d}",
        "title": "A claim",
        "statement": "Asserted.",
        "source": [{"ref": "SRC-0001"}],
        "state": "asserted",
        "confidence": "medium",
        "method": "document-review",
        "updated": TODAY,
    }
    fields.update(overrides)
    add(root, f"claims/CLM-{number:04d}-c.md", **fields)


def rfi(root: Path, number: int, asked: datetime.date, state: str = "open") -> None:
    add(
        root,
        f"rfi/RFI-{number:04d}-q.md",
        id=f"RFI-{number:04d}",
        title="Boundary diagram",
        question="Where is it?",
        asked_of="owner",
        asked_on=asked,
        state=state,
        updated=TODAY,
    )


def test_the_headline_carries_the_marking_and_the_phase(assessment: Path) -> None:
    first = status.render(assessment, TODAY).splitlines()[0]
    assert "Example System" in first
    assert "PROTECTED" in first


def test_shows_the_phase_and_how_many_criteria_are_met(assessment: Path) -> None:
    assert "phase: intake (0/2)" in status.render(assessment, TODAY)


def test_names_the_failing_criteria_and_who_is_failing_them(assessment: Path) -> None:
    text = status.render(assessment, TODAY)
    assert "[ ] system-context-captured" in text
    assert "notes/system-context.md" in text


def test_a_met_criterion_is_ticked(assessment: Path) -> None:
    (assessment / "notes" / "system-context.md").write_text("# Context\n")
    assert "[x] system-context-captured" in status.render(assessment, TODAY)


def test_counts_claims_by_state(assessment: Path) -> None:
    claim(assessment, 1)
    claim(assessment, 2, state="draft")
    assert "asserted 1" in status.render(assessment, TODAY)
    assert "draft 1" in status.render(assessment, TODAY)


def test_flags_claims_nothing_bears_on(assessment: Path) -> None:
    claim(assessment, 1)
    assert "1 claim with no evidence" in status.render(assessment, TODAY)


def test_a_claim_with_evidence_is_not_flagged(assessment: Path) -> None:
    claim(assessment, 1)
    add(
        assessment,
        "evidence/EVD-0001-e.md",
        id="EVD-0001",
        title="Export",
        bears_on=["CLM-0001"],
        direction="supports",
        artifact=["inbox/export.json"],
        method="config-review",
        collected=TODAY,
        collected_by="owner",
        state="accepted",
        updated=TODAY,
    )
    assert "claim with no evidence" not in status.render(assessment, TODAY)


def test_flags_ad_hoc_handling_and_low_confidence(assessment: Path) -> None:
    claim(assessment, 1, method="ad-hoc", confidence="low")
    text = status.render(assessment, TODAY)
    assert "1 low confidence" in text
    assert "1 ad-hoc" in text


def test_lists_open_rfis_oldest_first_with_their_age(assessment: Path) -> None:
    rfi(assessment, 1, datetime.date(2026, 8, 19))
    rfi(assessment, 2, datetime.date(2026, 8, 30))
    lines = [line for line in status.render(assessment, TODAY).splitlines() if "RFI-" in line]
    assert lines[0].split()[:2] == ["RFI-0001", "14d"]
    assert lines[1].split()[:2] == ["RFI-0002", "3d"]


def test_an_answered_rfi_is_not_listed_as_open(assessment: Path) -> None:
    rfi(assessment, 1, datetime.date(2026, 8, 19), state="answered")
    assert "RFI-0001" not in status.render(assessment, TODAY)


def test_shows_the_last_three_decisions_newest_first(assessment: Path) -> None:
    (assessment / "decisions.md").write_text(
        "# Decisions\n\n"
        "## 2026-08-14 — Use the moderate baseline\n\nBecause.\n\n"
        "## 2026-08-21 — Accept RSK-0004\n\nBecause.\n\n"
        "## 2026-08-28 — Treat AD as inherited\n\nBecause.\n\n"
        "## 2026-09-01 — Narrow the boundary\n\nBecause.\n"
    )
    text = status.render(assessment, TODAY)
    assert "2026-09-01  Narrow the boundary" in text
    assert "Use the moderate baseline" not in text


def test_counts_what_is_waiting_in_the_inbox(assessment: Path) -> None:
    (assessment / "inbox" / "ssp.pdf").write_text("x")
    assert "1 file waiting" in status.render(assessment, TODAY)


def test_warns_while_the_configuration_is_still_a_placeholder(assessment: Path) -> None:
    assert "risk-matrix.yaml is a placeholder" in status.render(assessment, TODAY)


def test_the_warning_goes_away_once_the_team_has_signed_it_off(assessment: Path) -> None:
    matrix = assessment / "risk-matrix.yaml"
    matrix.write_text(matrix.read_text().replace("review-required: true", "review-required: false"))
    assert "risk-matrix.yaml is a placeholder" not in status.render(assessment, TODAY)


def test_fits_on_one_screen(assessment: Path) -> None:
    for number in range(1, 30):
        claim(assessment, number)
        rfi(assessment, number, datetime.date(2026, 8, 1))
    lines = status.render(assessment, TODAY).splitlines()
    assert len(lines) <= 40
    assert max(len(line) for line in lines) <= 100


def test_json_carries_the_same_numbers_for_other_tools(assessment: Path) -> None:
    claim(assessment, 1, state="draft")
    data = status.summary(assessment, TODAY)
    assert data["phase"] == "intake"
    assert data["claims"]["draft"] == 1
    assert data["criteria"][0]["passed"] is False


def test_a_broken_assessment_still_renders(assessment: Path) -> None:
    (assessment / "assessment.yaml").write_text("classification:\n\tdata: bad\n")
    assert "unreadable" in status.render(assessment, TODAY)


def test_only_documents_that_have_not_been_ingested_count_as_waiting(
    assessment: Path,
) -> None:
    from ato_assist import ingest

    (assessment / "inbox" / "ssp.md").write_text("# SSP\n\nText.\n")
    ingest.run(assessment)
    # The original stays on disk under the default retention policy; it is not waiting.
    assert "waiting" not in status.render(assessment, TODAY)
    (assessment / "inbox" / "policy.md").write_text("# Policy\n\nMore.\n")
    assert "1 file waiting" in status.render(assessment, TODAY)


def test_control_coverage_counts_against_the_framework_profile_not_the_files(
    assessment: Path,
) -> None:
    add(
        assessment,
        "controls/ism/ISM-0421.md",
        id="ISM-0421",
        framework="ism",
        title="Authentication",
        status="satisfied",
        claims=["CLM-0001"],
        confidence="medium",
        method="document-review",
        updated=TODAY,
    )
    line = next(
        line for line in status.render(assessment, TODAY).splitlines() if "controls" in line
    )
    # One assessed control out of every ISM control that applies at PROTECTED.
    assert "1/" in line
    assert "/1 " not in line
    assert "%" in line


def _risk(root: Path, number: int, likelihood: str, impact: str, **overrides: object) -> None:
    fields: dict[str, object] = {
        "id": f"RSK-{number:04d}",
        "title": "A risk",
        "statement": "Something.",
        "threat": "T",
        "vulnerability": "V",
        "consequence": "C",
        "likelihood": likelihood,
        "impact": impact,
        "refs": ["CLM-0001"],
        "state": "open",
        "owner": "someone",
        "updated": TODAY,
    }
    fields.update(overrides)
    add(root, f"risks/RSK-{number:04d}-r.md", **fields)


def test_risks_are_counted_by_derived_severity_not_by_a_stored_rating(
    assessment: Path,
) -> None:
    _risk(assessment, 1, "almost-certain", "severe")
    _risk(assessment, 2, "rare", "minor")
    line = next(line for line in status.render(assessment, TODAY).splitlines() if "risks" in line)
    assert "extreme 1" in line
    assert "low 1" in line


def test_a_risk_rated_off_the_matrix_scales_is_flagged(assessment: Path) -> None:
    _risk(assessment, 1, "quite likely", "severe")
    assert "not on the matrix scales" in status.render(assessment, TODAY)
