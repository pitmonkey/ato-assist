"""checks — exit criteria a script can decide, with no model in the loop."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from ato_assist import checks, repo, scaffold
from tests_support import SPEC

TODAY = datetime.date(2026, 9, 2)


@pytest.fixture
def assessment(tmp_path: Path) -> Path:
    scaffold.create(tmp_path, SPEC)
    return tmp_path


def add(root: Path, relative: str, **fields: object) -> None:
    from ato_assist import frontmatter

    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.render(dict(fields), "Body.\n"))


def claim(root: Path, number: int, state: str = "asserted", source: str = "SRC-0001") -> None:
    add(
        root,
        f"claims/CLM-{number:04d}-c.md",
        id=f"CLM-{number:04d}",
        title="A claim",
        statement="Something is asserted.",
        source=[{"ref": source}],
        state=state,
        confidence="medium",
        method="document-review",
        updated=TODAY,
    )


def source(root: Path, number: int) -> None:
    add(
        root,
        f"sources/SRC-{number:04d}-doc/index.md",
        id=f"SRC-{number:04d}",
        title="A document",
        kind="document",
        received=TODAY,
        origin="owner",
        classification="PROTECTED",
        hash="sha256:abc",
        state="ingested",
        updated=TODAY,
    )


def run(root: Path, check: str, **args: object) -> checks.CheckResult:
    index = repo.RepoIndex(root)
    criterion = {"id": "c1", "check": check, "args": args}
    return checks.evaluate(index, criterion, today=TODAY)


def test_field_count_counts_items_matching_a_value(assessment: Path) -> None:
    claim(assessment, 1, state="draft")
    claim(assessment, 2, state="asserted")
    result = run(assessment, "field_count", dir="claims", field="state", equals="draft", max=0)
    assert result.passed is False
    assert result.actual == "1"
    assert result.offenders == ["claims/CLM-0001-c.md"]


def test_field_count_passes_when_the_bound_is_met(assessment: Path) -> None:
    claim(assessment, 1)
    assert run(
        assessment, "field_count", dir="claims", field="state", equals="draft", max=0
    ).passed


def test_field_count_with_a_minimum_counts_anything_carrying_the_field(
    assessment: Path,
) -> None:
    source(assessment, 1)
    assert run(assessment, "field_count", dir="sources", field="state", min=1).passed


def test_no_orphans_names_the_items_nobody_cites(assessment: Path) -> None:
    source(assessment, 1)
    source(assessment, 2)
    claim(assessment, 1, source="SRC-0001")
    result = run(
        assessment, "no_orphans", **{"from": "sources", "referenced_by": "claims", "via": "source"}
    )
    assert result.passed is False
    assert result.offenders == ["sources/SRC-0002-doc/index.md"]


def test_no_orphans_ignores_an_anchor_when_matching(assessment: Path) -> None:
    source(assessment, 1)
    claim(assessment, 1, source="SRC-0001#access-control")
    assert run(
        assessment, "no_orphans", **{"from": "sources", "referenced_by": "claims", "via": "source"}
    ).passed


def test_no_orphans_can_be_narrowed_to_a_subset(assessment: Path) -> None:
    source(assessment, 1)
    add(
        assessment,
        "sources/SRC-0002-doc/index.md",
        id="SRC-0002",
        title="Superseded",
        kind="document",
        received=TODAY,
        origin="owner",
        classification="PROTECTED",
        hash="sha256:def",
        state="superseded",
        updated=TODAY,
    )
    claim(assessment, 1, source="SRC-0001")
    assert run(
        assessment,
        "no_orphans",
        **{
            "from": "sources",
            "referenced_by": "claims",
            "via": "source",
            "where": {"state": "ingested"},
        },
    ).passed


def test_required_ref_finds_items_citing_too_little(assessment: Path) -> None:
    add(
        assessment,
        "controls/ism/ISM-0421.md",
        id="ISM-0421",
        framework="ism",
        title="A control",
        status="satisfied",
        claims=["CLM-0001"],
        confidence="medium",
        method="document-review",
        updated=TODAY,
    )
    result = run(
        assessment,
        "required_ref",
        dir="controls",
        field="evidence",
        min=1,
        where={"status": "satisfied"},
    )
    assert result.passed is False
    assert result.offenders == ["controls/ism/ISM-0421.md"]


def test_age_max_flags_only_what_is_too_old(assessment: Path) -> None:
    for number, asked in ((1, datetime.date(2026, 8, 1)), (2, datetime.date(2026, 9, 1))):
        add(
            assessment,
            f"rfi/RFI-{number:04d}-q.md",
            id=f"RFI-{number:04d}",
            title="A question",
            question="Why?",
            asked_of="owner",
            asked_on=asked,
            state="open",
            updated=TODAY,
        )
    result = run(
        assessment,
        "age_max",
        dir="rfi",
        where={"state": "open"},
        date_field="asked_on",
        max_days=21,
    )
    assert result.passed is False
    assert result.offenders == ["rfi/RFI-0001-q.md"]


def test_file_exists_interpolates_the_short_name(assessment: Path) -> None:
    (assessment / "outputs" / "exs-report.md").write_text("x")
    assert run(assessment, "file_exists", path="outputs/{short_name}-report.md").passed


def test_file_exists_fails_when_the_file_is_empty(assessment: Path) -> None:
    (assessment / "outputs" / "exs-report.md").write_text("")
    assert not run(assessment, "file_exists", path="outputs/{short_name}-report.md").passed


def test_an_unknown_check_fails_rather_than_crashing(assessment: Path) -> None:
    result = run(assessment, "invented_check", dir="claims")
    assert result.passed is False
    assert "unknown" in result.actual


def test_a_check_given_nonsense_arguments_fails_rather_than_crashing(
    assessment: Path,
) -> None:
    result = run(assessment, "field_count", dir="claims", field="state", max="not a number")
    assert result.passed is False


def test_the_current_phase_reports_every_criterion(assessment: Path) -> None:
    index = repo.RepoIndex(assessment)
    results = checks.evaluate_phase(index, "intake", today=TODAY)
    assert [r.criterion_id for r in results] == ["system-context-captured", "sources-ingested"]
    assert not any(r.passed for r in results)


def test_an_unknown_phase_reports_nothing_rather_than_raising(assessment: Path) -> None:
    assert checks.evaluate_phase(repo.RepoIndex(assessment), "invented", today=TODAY) == []


def test_a_ceiling_over_an_empty_collection_is_not_yet_applicable(
    assessment: Path,
) -> None:
    """"No claim is still a draft" is trivially true with no claims, and means nothing."""
    result = run(assessment, "field_count", dir="claims", field="state", equals="draft", max=0)
    assert result.applicable is False


def test_a_ceiling_becomes_applicable_once_the_collection_has_something_in_it(
    assessment: Path,
) -> None:
    claim(assessment, 1)
    result = run(assessment, "field_count", dir="claims", field="state", equals="draft", max=0)
    assert result.applicable is True
    assert result.passed is True


def test_a_floor_is_always_applicable(assessment: Path) -> None:
    """"At least one source ingested" is a real, failable statement about an empty repo."""
    result = run(assessment, "field_count", dir="sources", field="state", min=1)
    assert result.applicable is True
    assert result.passed is False


def test_no_orphans_over_nothing_is_not_yet_applicable(assessment: Path) -> None:
    result = run(
        assessment, "no_orphans", **{"from": "sources", "referenced_by": "claims", "via": "source"}
    )
    assert result.applicable is False


def test_required_ref_over_nothing_is_not_yet_applicable(assessment: Path) -> None:
    result = run(assessment, "required_ref", dir="controls", field="evidence", min=1)
    assert result.applicable is False


def test_age_max_over_nothing_is_not_yet_applicable(assessment: Path) -> None:
    result = run(assessment, "age_max", dir="rfi", date_field="asked_on", max_days=21)
    assert result.applicable is False


def test_file_exists_is_always_applicable(assessment: Path) -> None:
    assert run(assessment, "file_exists", path="notes/anything.md").applicable is True
