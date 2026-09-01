"""The `ato` command line: what the skills actually invoke."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ato_assist import cli
from tests_support import SPEC

INIT_ARGS = [
    "--name", SPEC.name,
    "--short-name", SPEC.short_name,
    "--owner", SPEC.owner,
    "--assessor", SPEC.assessor,
    "--data", SPEC.data,
    "--environment", SPEC.environment,
    "--marking", SPEC.marking,
]


def test_init_scaffolds_and_reports_where(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["init", str(tmp_path), *INIT_ARGS]) == 0
    assert (tmp_path / "assessment.yaml").is_file()
    assert str(tmp_path) in capsys.readouterr().out


def test_init_refuses_an_impossible_marking(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = list(INIT_ARGS)
    args[args.index("--marking") + 1] = "OFFICIAL"
    assert cli.main(["init", str(tmp_path), *args]) == 2
    assert "PROTECTED" in capsys.readouterr().err
    assert not (tmp_path / "assessment.yaml").exists()


def test_validate_is_quiet_and_zero_for_a_clean_assessment(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["init", str(tmp_path), *INIT_ARGS])
    capsys.readouterr()
    assert cli.main(["validate", str(tmp_path)]) == 0
    assert "0 problems" in capsys.readouterr().out


def test_validate_reports_a_broken_file_and_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["init", str(tmp_path), *INIT_ARGS])
    (tmp_path / "claims" / "CLM-0001-broken.md").write_text("no frontmatter\n")
    capsys.readouterr()
    assert cli.main(["validate", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "ATO-E101" in out
    assert "claims/CLM-0001-broken.md" in out


def test_validate_emits_json_on_request(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["init", str(tmp_path), *INIT_ARGS])
    (tmp_path / "claims" / "CLM-0001-broken.md").write_text("no frontmatter\n")
    capsys.readouterr()
    cli.main(["validate", str(tmp_path), "--json"])
    findings = json.loads(capsys.readouterr().out)["findings"]
    assert findings[0]["code"] == "ATO-E101"


def test_validate_outside_an_assessment_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["validate", str(tmp_path)]) == 2
    assert "assessment" in capsys.readouterr().err


def test_next_id_starts_at_one_and_then_follows_what_exists(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["init", str(tmp_path), *INIT_ARGS])
    capsys.readouterr()
    cli.main(["next-id", "claims", "--root", str(tmp_path)])
    assert capsys.readouterr().out.strip() == "CLM-0001"
    (tmp_path / "claims" / "CLM-0007-a.md").write_text("x")
    cli.main(["next-id", "claims", "--root", str(tmp_path)])
    assert capsys.readouterr().out.strip() == "CLM-0008"


def test_no_arguments_prints_usage_and_exits_two(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([]) == 2
    assert "usage" in capsys.readouterr().err.lower()
