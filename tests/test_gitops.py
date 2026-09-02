"""gitops — the commits the workbench makes on the assessor's behalf."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ato_assist import gitops, scaffold
from tests_support import SPEC


@pytest.fixture
def assessment(tmp_path: Path) -> Path:
    scaffold.create(tmp_path, SPEC)
    return tmp_path


def log(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--format=%s"], cwd=root, capture_output=True, text=True, check=True
    )
    return result.stdout.splitlines()


def test_a_commit_is_prefixed_by_what_kind_of_step_it_was(assessment: Path) -> None:
    (assessment / "notes" / "a.md").write_text("x")
    gitops.commit(assessment, "ingest", "SSP v2.4 (3 new sections, 2 changed)")
    assert log(assessment)[0] == "ingest: SSP v2.4 (3 new sections, 2 changed)"


def test_nothing_to_commit_is_reported_not_raised(assessment: Path) -> None:
    assert gitops.commit(assessment, "ingest", "nothing changed") is False
    assert len(log(assessment)) == 1


def test_an_unknown_kind_is_refused_so_the_log_stays_scannable(assessment: Path) -> None:
    (assessment / "notes" / "a.md").write_text("x")
    with pytest.raises(gitops.GitError) as excinfo:
        gitops.commit(assessment, "misc", "something")
    assert "ingest" in str(excinfo.value)


def test_the_body_records_which_session_made_the_change(assessment: Path) -> None:
    (assessment / "notes" / "a.md").write_text("x")
    gitops.commit(assessment, "phase", "intake -> claims-extraction", detail="2 criteria met")
    body = subprocess.run(
        ["git", "log", "-1", "--format=%b"], cwd=assessment, capture_output=True, text=True
    ).stdout
    assert "2 criteria met" in body


def test_outside_a_repository_it_says_so(tmp_path: Path) -> None:
    (tmp_path / "assessment.yaml").write_text("phase: intake\n")
    with pytest.raises(gitops.GitError):
        gitops.commit(tmp_path, "ingest", "x")


def test_reviewing_existing_work_is_its_own_step(assessment: Path) -> None:
    """Moving claims out of draft is the assessor's review, not more extraction."""
    (assessment / "notes" / "a.md").write_text("x")
    gitops.commit(assessment, "review", "39 claims accepted, 2 withdrawn")
    assert log(assessment)[0].startswith("review:")
