"""risk — the likelihood/consequence matrix, and severity derived from it."""

from __future__ import annotations

from pathlib import Path

import pytest

from ato_assist import risk, scaffold
from tests_support import SPEC


@pytest.fixture
def assessment(tmp_path: Path) -> Path:
    scaffold.create(tmp_path, SPEC)
    return tmp_path


def test_loads_the_scales_the_assessment_carries(assessment: Path) -> None:
    matrix = risk.load(assessment)
    assert matrix.likelihood[0] == "rare"
    assert "severe" in matrix.impact


def test_severity_comes_from_the_matrix(assessment: Path) -> None:
    assert risk.load(assessment).severity("possible", "severe") == "extreme"


def test_an_unknown_likelihood_has_no_severity_rather_than_a_guessed_one(
    assessment: Path,
) -> None:
    assert risk.load(assessment).severity("catastrophic", "severe") is None


def test_severities_are_ordered_so_a_register_can_be_sorted(assessment: Path) -> None:
    matrix = risk.load(assessment)
    assert matrix.rank("extreme") > matrix.rank("low")


def test_a_missing_matrix_is_reported_not_guessed(tmp_path: Path) -> None:
    with pytest.raises(risk.MatrixError):
        risk.load(tmp_path)


def test_the_shipped_matrix_is_flagged_as_needing_review(assessment: Path) -> None:
    assert risk.load(assessment).review_required is True


def test_every_combination_of_the_scales_has_a_rating(assessment: Path) -> None:
    matrix = risk.load(assessment)
    missing = [
        (likelihood, impact)
        for likelihood in matrix.likelihood
        for impact in matrix.impact
        if matrix.severity(likelihood, impact) is None
    ]
    assert missing == []


def test_a_risk_file_is_rated_from_its_own_fields(assessment: Path) -> None:
    from ato_assist import frontmatter

    (assessment / "risks" / "RSK-0001-a.md").write_text(
        frontmatter.render(
            {
                "id": "RSK-0001",
                "title": "A risk",
                "statement": "Something.",
                "threat": "T",
                "vulnerability": "V",
                "consequence": "C",
                "likelihood": "likely",
                "impact": "severe",
                "refs": ["CLM-0001"],
                "state": "open",
                "owner": "someone",
                "updated": "2026-09-02",
            },
            "",
        )
    )
    rated = risk.rate_all(assessment)
    assert rated[0].id == "RSK-0001"
    assert rated[0].severity == "extreme"


def test_a_risk_using_a_scale_the_matrix_does_not_have_is_reported(
    assessment: Path,
) -> None:
    from ato_assist import frontmatter

    (assessment / "risks" / "RSK-0001-a.md").write_text(
        frontmatter.render(
            {
                "id": "RSK-0001",
                "title": "A risk",
                "statement": "Something.",
                "threat": "T",
                "vulnerability": "V",
                "consequence": "C",
                "likelihood": "quite likely",
                "impact": "severe",
                "refs": ["CLM-0001"],
                "state": "draft",
                "updated": "2026-09-02",
            },
            "",
        )
    )
    rated = risk.rate_all(assessment)
    assert rated[0].severity is None
    assert "quite likely" in rated[0].problem
