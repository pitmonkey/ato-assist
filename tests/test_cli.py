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
    assert "0 problems (0 blocking)" in capsys.readouterr().out


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


def test_ingest_reports_what_it_did(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["init", str(tmp_path), *INIT_ARGS])
    (tmp_path / "inbox" / "ssp.md").write_text("# SSP\n\nThe SIEM logs everything.\n")
    capsys.readouterr()
    assert cli.main(["ingest", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "SRC-0001" in out
    assert "1 term" in out


def test_ingest_surfaces_questions_it_could_not_answer_itself(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["init", str(tmp_path), *INIT_ARGS])
    (tmp_path / "inbox" / "diagram.vsdx").write_bytes(b"\x00binary")
    capsys.readouterr()
    cli.main(["ingest", str(tmp_path)])
    assert "diagram.vsdx" in capsys.readouterr().out


def test_controls_search_returns_candidates_for_mapping(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["controls", "--search", "multi-factor authentication"]) == 0
    out = capsys.readouterr().out
    assert "ISM-" in out
    assert len(out.splitlines()) <= 21  # a shortlist to judge, not a catalogue dump


def test_controls_profile_reports_how_many_apply(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["controls", "--profile", "PROTECTED"]) == 0
    assert "apply at PROTECTED" in capsys.readouterr().out


def test_controls_shows_one_control_in_full(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["controls", "ISM-0421"]) == 0
    out = capsys.readouterr().out
    assert "ISM-0421" in out
    assert "applies at" in out


def test_an_unknown_control_exits_one(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["controls", "ISM-9999"]) == 1
    assert "ISM-9999" in capsys.readouterr().err


def test_controls_reports_the_catalogue_version(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["controls", "--profile", "PROTECTED"])
    assert "ISM " in capsys.readouterr().out


def test_risk_scales_warns_while_the_matrix_is_a_placeholder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["init", str(tmp_path), *INIT_ARGS])
    capsys.readouterr()
    assert cli.main(["risk", "scales", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "almost-certain" in out
    assert "placeholder" in out


def test_export_writes_the_register_and_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["init", str(tmp_path), *INIT_ARGS])
    capsys.readouterr()
    assert cli.main(["export", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "exs-risk-register.csv" in out
    assert "exs-report.md" in out


def test_evidence_add_writes_a_conformant_entry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from ato_assist import repo, validate

    cli.main(["init", str(tmp_path), *INIT_ARGS])
    artifact = tmp_path / "inbox" / "ca-policies.json"
    artifact.write_text("{}")
    capsys.readouterr()
    assert cli.main([
        "evidence", "add", "--root", str(tmp_path), "--file", str(artifact),
        "--describe", "Conditional access policy export", "--bears-on", "CLM-0042",
    ]) == 0
    assert "EVD-0001" in capsys.readouterr().out
    path = next((tmp_path / "evidence").glob("EVD-0001-*.md"))
    relative = repo.relative(tmp_path, path)
    assert validate.validate_document(relative, path.read_text()) == []


def test_evidence_add_records_the_hash_of_what_it_saw(tmp_path: Path) -> None:
    from ato_assist import frontmatter

    cli.main(["init", str(tmp_path), *INIT_ARGS])
    artifact = tmp_path / "inbox" / "scan.json"
    artifact.write_text("{}")
    cli.main([
        "evidence", "add", "--root", str(tmp_path), "--file", str(artifact),
        "--describe", "A scan", "--bears-on", "CLM-0001",
    ])
    data, _ = frontmatter.parse(next((tmp_path / "evidence").glob("EVD-0001-*.md")).read_text())
    assert str(data["integrity"]).startswith("sha256:")
    assert data["method"] == "ad-hoc"


def test_evidence_add_refuses_a_file_it_cannot_see(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["init", str(tmp_path), *INIT_ARGS])
    capsys.readouterr()
    assert cli.main([
        "evidence", "add", "--root", str(tmp_path), "--file", str(tmp_path / "absent.json"),
        "--describe", "x", "--bears-on", "CLM-0001",
    ]) == 2
    assert "absent.json" in capsys.readouterr().err


def test_controls_rejects_a_profile_that_is_not_in_the_catalogue(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A profile that means nothing must not look like one that matches no controls."""
    assert cli.main(["controls", "--profile", "banana"]) == 1
    err = capsys.readouterr().err
    assert "banana" in err
    assert "PROTECTED" in err  # the vocabulary is named


def test_controls_accepts_a_profile_typed_in_the_wrong_case(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["controls", "--profile", "official: sensitive"]) == 0
    assert "apply at OFFICIAL:Sensitive" in capsys.readouterr().out


def test_init_rejects_a_profile_that_matches_no_framework_profile(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = [*INIT_ARGS, "--profile", "banana"]
    assert cli.main(["init", str(tmp_path), *args]) == 2
    assert "banana" in capsys.readouterr().err
    assert not (tmp_path / "assessment.yaml").exists()


def test_init_writes_the_canonical_profile_whatever_the_assessor_typed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from ato_assist import repo

    cli.main(["init", str(tmp_path), *INIT_ARGS, "--profile", "protected"])
    capsys.readouterr()
    assessment = repo.load_assessment(tmp_path)
    assert assessment is not None
    assert assessment["frameworks"][0]["profile"] == "PROTECTED"


def test_init_echoes_what_it_recorded(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The profile defect was invisible because nothing read the settings back."""
    cli.main(["init", str(tmp_path), *INIT_ARGS])
    out = capsys.readouterr().out
    for expected in (SPEC.name, SPEC.owner, SPEC.assessor, "OFFICIAL:Sensitive",
                     "PROTECTED", "ism", "gitignore"):
        assert expected in out, expected


def test_init_says_how_many_controls_the_profile_selects(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["init", str(tmp_path), *INIT_ARGS])
    assert "controls apply" in capsys.readouterr().out


def test_init_warns_about_the_placeholder_configuration_itself(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The warning must survive an agent that skips the skill's final step."""
    cli.main(["init", str(tmp_path), *INIT_ARGS])
    out = capsys.readouterr().out
    assert "risk-matrix.yaml" in out
    assert "placeholder" in out
