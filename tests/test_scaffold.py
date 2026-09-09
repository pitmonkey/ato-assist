"""scaffold — turning an empty directory into an assessment repository."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ato_assist import repo, scaffold, validate
from tests_support import SPEC


def test_creates_every_contract_directory(tmp_path: Path) -> None:
    scaffold.create(tmp_path, SPEC)
    for name in ("sources", "claims", "evidence", "controls", "risks", "rfi",
                 "inbox", "notes", "outputs", "glossary"):
        assert (tmp_path / name).is_dir(), name


def test_empty_directories_are_kept_by_a_readme_not_a_dotfile(tmp_path: Path) -> None:
    scaffold.create(tmp_path, SPEC)
    keeper = tmp_path / "claims" / "README.md"
    assert keeper.is_file()
    assert "claim" in keeper.read_text().lower()


def test_writes_an_assessment_that_passes_the_classification_gate(tmp_path: Path) -> None:
    scaffold.create(tmp_path, SPEC)
    assessment = repo.load_assessment(tmp_path)
    assert assessment is not None
    assert assessment["classification"]["marking"] == "PROTECTED"
    assert validate.classification_gate("claims/CLM-0001-a.md", assessment) == []


def test_refuses_a_marking_below_the_data_it_carries(tmp_path: Path) -> None:
    spec = SPEC._replace(marking="OFFICIAL")
    with pytest.raises(scaffold.ScaffoldError) as excinfo:
        scaffold.create(tmp_path, spec)
    assert "PROTECTED" in str(excinfo.value)
    assert not (tmp_path / "assessment.yaml").exists()


def test_refuses_an_unknown_marking(tmp_path: Path) -> None:
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.create(tmp_path, SPEC._replace(environment="COSMIC"))


def test_refuses_to_scaffold_over_an_existing_assessment(tmp_path: Path) -> None:
    scaffold.create(tmp_path, SPEC)
    with pytest.raises(scaffold.ScaffoldError) as excinfo:
        scaffold.create(tmp_path, SPEC)
    assert "already" in str(excinfo.value)


def test_copies_the_org_configuration_into_the_assessment(tmp_path: Path) -> None:
    scaffold.create(tmp_path, SPEC)
    assert (tmp_path / "process.yaml").is_file()
    assert (tmp_path / "risk-matrix.yaml").is_file()
    assert (tmp_path / "register-columns.yaml").is_file()
    assert "review-required: true" in (tmp_path / "risk-matrix.yaml").read_text()


def test_the_workspace_claude_md_carries_the_marking(tmp_path: Path) -> None:
    scaffold.create(tmp_path, SPEC)
    text = (tmp_path / "CLAUDE.md").read_text()
    assert "PROTECTED" in text
    assert "Example System" in text
    assert "{marking}" not in text


def test_seeds_the_working_files(tmp_path: Path) -> None:
    scaffold.create(tmp_path, SPEC)
    assert (tmp_path / "decisions.md").is_file()
    assert (tmp_path / "tooling-gaps.md").is_file()
    assert (tmp_path / "glossary.md").is_file()
    assert (tmp_path / "glossary" / "unresolved.md").is_file()


def test_gitignores_inbox_originals_by_default(tmp_path: Path) -> None:
    scaffold.create(tmp_path, SPEC)
    ignored = (tmp_path / ".gitignore").read_text()
    assert "inbox/" in ignored
    assert ".ato/" in ignored


def test_committing_inbox_originals_leaves_them_tracked(tmp_path: Path) -> None:
    scaffold.create(tmp_path, SPEC._replace(retain="commit"))
    assert "inbox/" not in (tmp_path / ".gitignore").read_text()
    assert repo.load_assessment(tmp_path)["inbox"]["retain"] == "commit"  # type: ignore[index]


def test_initialises_git_with_one_commit(tmp_path: Path) -> None:
    scaffold.create(tmp_path, SPEC)
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True
    )
    assert log.returncode == 0
    assert log.stdout.count("\n") == 1
    assert "Example System" in log.stdout


def test_leaves_an_existing_git_repository_alone(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    scaffold.create(tmp_path, SPEC)
    assert (tmp_path / ".git").is_dir()


def test_the_scaffolded_assessment_parses_under_the_yaml_subset(tmp_path: Path) -> None:
    scaffold.create(tmp_path, SPEC)
    for name in ("assessment.yaml", "process.yaml", "risk-matrix.yaml"):
        assert repo.load_yaml(tmp_path / name) is not None, name


def test_creates_a_directory_for_each_configured_framework(tmp_path: Path) -> None:
    scaffold.create(tmp_path, SPEC)
    assert (tmp_path / "controls" / "ism").is_dir()
    assert "ism" in (tmp_path / "controls" / "ism" / "README.md").read_text()
