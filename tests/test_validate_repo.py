"""L2 and L3: the checks that need to look at more than one file."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from ato_assist import frontmatter, repo, scaffold, validate
from tests_support import SPEC

TODAY = datetime.date(2026, 9, 2)


@pytest.fixture
def assessment(tmp_path: Path) -> Path:
    scaffold.create(tmp_path, SPEC)
    _source(tmp_path, 1)
    return tmp_path


def _write(root: Path, relative: str, body: str = "Body.\n", **fields: object) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.render(dict(fields), body))
    return path


def _source(root: Path, number: int, body: str = "## Access control\n\nText.\n") -> Path:
    return _write(
        root,
        f"sources/SRC-{number:04d}-doc/index.md",
        body,
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


def _claim(root: Path, number: int, ref: str) -> Path:
    return _write(
        root,
        f"claims/CLM-{number:04d}-c.md",
        id=f"CLM-{number:04d}",
        title="A claim",
        statement="Asserted.",
        source=[{"ref": ref}],
        state="asserted",
        confidence="medium",
        method="document-review",
        updated=TODAY,
    )


def codes(findings: list[validate.Finding]) -> list[str]:
    return [finding.code for finding in findings]


def test_a_reference_to_something_that_exists_is_clean(assessment: Path) -> None:
    path = _claim(assessment, 1, "SRC-0001")
    index = repo.RepoIndex(assessment)
    relative = repo.relative(assessment, path)
    assert validate.validate_document(relative, path.read_text(), index) == []


def test_a_reference_to_a_target_that_does_not_exist_warns_rather_than_denies(
    assessment: Path,
) -> None:
    path = _claim(assessment, 1, "SRC-0099")
    index = repo.RepoIndex(assessment)
    findings = validate.validate_document(repo.relative(assessment, path), path.read_text(), index)
    assert codes(findings) == ["ATO-E112"]
    assert findings[0].level == "warn"


def test_an_anchor_that_does_not_match_a_heading_warns(assessment: Path) -> None:
    path = _claim(assessment, 1, "SRC-0001#backup-and-recovery")
    index = repo.RepoIndex(assessment)
    findings = validate.validate_document(repo.relative(assessment, path), path.read_text(), index)
    assert codes(findings) == ["ATO-E113"]


def test_an_anchor_that_matches_a_heading_in_a_chunk_is_clean(assessment: Path) -> None:
    (assessment / "sources" / "SRC-0001-doc" / "01-access-control.md").write_text(
        "## Access control\n\nText.\n"
    )
    path = _claim(assessment, 1, "SRC-0001#access-control")
    index = repo.RepoIndex(assessment)
    relative = repo.relative(assessment, path)
    assert validate.validate_document(relative, path.read_text(), index) == []


def test_an_id_already_used_by_another_file_is_denied(assessment: Path) -> None:
    _claim(assessment, 1, "SRC-0001")
    index = repo.RepoIndex(assessment)
    duplicate = "claims/CLM-0001-different-slug.md"
    text = (assessment / "claims" / "CLM-0001-c.md").read_text()
    findings = validate.validate_document(duplicate, text, index)
    assert codes(findings) == ["ATO-E130"]
    assert findings[0].level == "error"


def test_the_hook_view_skips_the_checks_that_need_the_repository(assessment: Path) -> None:
    path = _claim(assessment, 1, "SRC-0099")
    assert validate.validate_document(repo.relative(assessment, path), path.read_text()) == []


def test_a_repo_sweep_reports_a_source_no_claim_cites(assessment: Path) -> None:
    findings = validate.validate_repo(assessment, TODAY)
    assert "ATO-E301" in codes(findings)


def test_a_repo_sweep_reports_evidence_whose_artifact_is_gone(assessment: Path) -> None:
    _claim(assessment, 1, "SRC-0001")
    _write(
        assessment,
        "evidence/EVD-0001-e.md",
        id="EVD-0001",
        title="Export",
        bears_on=["CLM-0001"],
        direction="supports",
        artifact=["evidence/artifacts/absent.json"],
        method="config-review",
        collected=TODAY,
        collected_by="owner",
        state="accepted",
        updated=TODAY,
    )
    findings = validate.validate_repo(assessment, TODAY)
    assert "ATO-E302" in codes(findings)


def test_a_repo_sweep_reports_a_risk_rated_off_the_matrix(assessment: Path) -> None:
    _claim(assessment, 1, "SRC-0001")
    _write(
        assessment,
        "risks/RSK-0001-r.md",
        id="RSK-0001",
        title="A risk",
        statement="Something.",
        threat="T",
        vulnerability="V",
        consequence="C",
        likelihood="quite likely",
        impact="major",
        refs=["CLM-0001"],
        state="draft",
        updated=TODAY,
    )
    findings = validate.validate_repo(assessment, TODAY)
    assert "ATO-E303" in codes(findings)


def test_a_repo_sweep_reports_a_control_in_a_framework_the_assessment_does_not_use(
    assessment: Path,
) -> None:
    _claim(assessment, 1, "SRC-0001")
    _write(
        assessment,
        "controls/e8/ML1-01.md",
        id="ML1-01",
        framework="e8",
        title="Patch applications",
        status="not-assessed",
        confidence="medium",
        method="document-review",
        updated=TODAY,
    )
    findings = validate.validate_repo(assessment, TODAY)
    assert "ATO-E304" in codes(findings)


def test_a_clean_assessment_sweeps_clean(assessment: Path) -> None:
    _claim(assessment, 1, "SRC-0001")
    assert validate.validate_repo(assessment, TODAY) == []


def test_a_framework_profile_that_selects_no_controls_is_blocking(
    assessment: Path,
) -> None:
    """Scaffolded wrong, worked on for weeks, noticed at control mapping. Catch it here."""
    path = assessment / "assessment.yaml"
    path.write_text(path.read_text().replace("profile: PROTECTED", "profile: banana"))
    findings = validate.validate_repo(assessment, TODAY)
    matching = [f for f in findings if f.code == "ATO-E305"]
    assert matching and matching[0].level == "error"
    assert "banana" in matching[0].message


def test_a_profile_spelled_unconventionally_is_a_tidy_up_not_a_failure(
    assessment: Path,
) -> None:
    path = assessment / "assessment.yaml"
    path.write_text(path.read_text().replace("profile: PROTECTED", "profile: protected"))
    matching = [f for f in validate.validate_repo(assessment, TODAY) if f.code == "ATO-E306"]
    assert matching and matching[0].level == "warn"
    assert "PROTECTED" in matching[0].message


def test_a_real_profile_is_not_flagged(assessment: Path) -> None:
    _claim(assessment, 1, "SRC-0001")
    assert "ATO-E305" not in codes(validate.validate_repo(assessment, TODAY))


def test_a_framework_with_no_catalogue_is_not_flagged(assessment: Path) -> None:
    """Only frameworks the plugin ships data for can be checked this way."""
    path = assessment / "assessment.yaml"
    path.write_text(path.read_text().replace("id: ism", "id: e8"))
    assert "ATO-E305" not in codes(validate.validate_repo(assessment, TODAY))
