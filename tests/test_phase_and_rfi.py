"""Moving the phase marker, and tracking requests for information."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from ato_assist import cli, frontmatter, repo
from tests_support import SPEC

TODAY = datetime.date(2026, 9, 2)

INIT = [
    "--name", SPEC.name, "--short-name", SPEC.short_name, "--owner", SPEC.owner,
    "--assessor", SPEC.assessor, "--data", SPEC.data, "--environment", SPEC.environment,
    "--marking", SPEC.marking,
]


@pytest.fixture
def assessment(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    cli.main(["init", str(tmp_path), *INIT])
    capsys.readouterr()
    return tmp_path


def phase_of(root: Path) -> str:
    assessment = repo.load_assessment(root)
    assert assessment is not None
    return str(assessment["phase"])


def test_phase_next_moves_the_marker_to_the_following_phase(assessment: Path) -> None:
    assert cli.main(["phase", "next", "--root", str(assessment)]) == 0
    assert phase_of(assessment) == "claims-extraction"


def test_phase_next_refuses_past_the_end(
    assessment: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for _ in range(6):
        cli.main(["phase", "next", "--root", str(assessment)])
    capsys.readouterr()
    assert cli.main(["phase", "next", "--root", str(assessment)]) == 1
    assert "last phase" in capsys.readouterr().err


def test_phase_next_records_the_move_in_decisions(assessment: Path) -> None:
    cli.main(["phase", "next", "--root", str(assessment)])
    assert "intake -> claims-extraction" in (assessment / "decisions.md").read_text()


def test_phase_set_goes_to_a_named_phase(assessment: Path) -> None:
    assert cli.main(["phase", "report", "--root", str(assessment)]) == 0
    assert phase_of(assessment) == "report"


def test_phase_set_refuses_a_phase_that_does_not_exist(
    assessment: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["phase", "invented", "--root", str(assessment)]) == 1
    assert "invented" in capsys.readouterr().err
    assert phase_of(assessment) == "intake"


def test_rfi_new_writes_a_tracked_question(
    assessment: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main([
        "rfi", "new", "--root", str(assessment),
        "--question", "Provide the conditional access policy export.",
        "--asked-of", "System owner", "--reason", "ISM-0421",
    ]) == 0
    assert "RFI-0001" in capsys.readouterr().out
    path = assessment / "rfi" / "RFI-0001-provide-the-conditional.md"
    data, _ = frontmatter.parse(path.read_text())
    assert data["state"] == "open"
    assert data["resolves"] == ["ISM-0421"]


def test_rfi_close_requires_the_answer_to_be_on_file(
    assessment: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main([
        "rfi", "new", "--root", str(assessment), "--question", "Where is the diagram?",
        "--asked-of", "owner",
    ])
    capsys.readouterr()
    assert cli.main(["rfi", "close", "RFI-0001", "--root", str(assessment)]) == 2
    assert "--source" in capsys.readouterr().err


def test_rfi_close_records_what_answered_it(
    assessment: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main([
        "rfi", "new", "--root", str(assessment), "--question", "Where is the diagram?",
        "--asked-of", "owner",
    ])
    capsys.readouterr()
    assert cli.main([
        "rfi", "close", "RFI-0001", "--source", "SRC-0011", "--root", str(assessment)
    ]) == 0
    path = next((assessment / "rfi").glob("RFI-0001-*.md"))
    data, _ = frontmatter.parse(path.read_text())
    assert data["state"] == "answered"
    assert data["answer_source"] == [{"ref": "SRC-0011"}]


def test_rfi_list_shows_open_questions_with_their_age(
    assessment: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main([
        "rfi", "new", "--root", str(assessment), "--question", "Where is the diagram?",
        "--asked-of", "owner",
    ])
    capsys.readouterr()
    cli.main(["rfi", "list", "--root", str(assessment)])
    assert "RFI-0001" in capsys.readouterr().out


def test_rfi_export_produces_a_message_the_assessor_can_send(
    assessment: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main([
        "rfi", "new", "--root", str(assessment),
        "--question", "Provide the conditional access policy export.",
        "--asked-of", "System owner",
    ])
    capsys.readouterr()
    cli.main(["rfi", "export", "--root", str(assessment)])
    out = capsys.readouterr().out
    assert "PROTECTED" in out  # the marking goes on anything leaving the assessment
    assert "RFI-0001" in out
    assert "Provide the conditional access policy export." in out
    assert "Example System" in out
