"""repo — locating an assessment, and the classification gate that guards it."""

from pathlib import Path

from ato_assist import repo, validate

ASSESSMENT = """schema: ato-assist/assessment@1
system:
  name: Example System
  short_name: exs
classification:
  data: OFFICIAL:Sensitive
  environment: PROTECTED
  marking: PROTECTED
phase: intake
"""


def make_repo(tmp_path: Path, assessment: str = ASSESSMENT) -> Path:
    (tmp_path / "claims").mkdir(parents=True)
    (tmp_path / "assessment.yaml").write_text(assessment)
    return tmp_path


def test_find_root_walks_up_from_a_file_inside_the_assessment(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    assert repo.find_root(root / "claims" / "CLM-0001-a.md") == root


def test_find_root_returns_none_outside_an_assessment(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    assert repo.find_root(tmp_path / "src" / "main.py") is None


def test_find_root_gives_up_rather_than_walking_to_the_filesystem_root(tmp_path: Path) -> None:
    deep = tmp_path / "a/b/c/d/e/f/g/h/i/j"
    deep.mkdir(parents=True)
    (tmp_path / "assessment.yaml").write_text(ASSESSMENT)
    assert repo.find_root(deep / "file.md") is None


def test_relative_path_is_posix_and_repo_rooted(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    assert repo.relative(root, root / "claims" / "CLM-0001-a.md") == "claims/CLM-0001-a.md"


def test_load_assessment_returns_the_mapping(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    loaded = repo.load_assessment(root)
    assert loaded is not None
    assert loaded["phase"] == "intake"


def test_load_assessment_returns_none_when_unparseable(tmp_path: Path) -> None:
    root = make_repo(tmp_path, "classification:\n\tdata: OFFICIAL\n")
    assert repo.load_assessment(root) is None


def test_a_complete_classification_passes_the_gate() -> None:
    assessment = {
        "classification": {
            "data": "OFFICIAL:Sensitive",
            "environment": "PROTECTED",
            "marking": "PROTECTED",
        }
    }
    assert validate.classification_gate("claims/CLM-0001-a.md", assessment) == []


def test_a_missing_classification_field_is_e001() -> None:
    assessment = {"classification": {"data": "PROTECTED", "environment": "PROTECTED"}}
    findings = validate.classification_gate("claims/CLM-0001-a.md", assessment)
    assert [f.code for f in findings] == ["ATO-E001"]
    assert "marking" in findings[0].message


def test_an_unreadable_assessment_is_e001() -> None:
    findings = validate.classification_gate("claims/CLM-0001-a.md", None)
    assert [f.code for f in findings] == ["ATO-E001"]


def test_a_marking_below_the_data_it_carries_is_e001() -> None:
    assessment = {
        "classification": {
            "data": "PROTECTED",
            "environment": "OFFICIAL",
            "marking": "OFFICIAL",
        }
    }
    findings = validate.classification_gate("claims/CLM-0001-a.md", assessment)
    assert [f.code for f in findings] == ["ATO-E001"]
    assert "PROTECTED" in findings[0].message


def test_a_marking_off_the_scale_is_e001() -> None:
    assessment = {
        "classification": {"data": "OFFICIAL", "environment": "OFFICIAL", "marking": "SUPER"}
    }
    findings = validate.classification_gate("claims/CLM-0001-a.md", assessment)
    assert [f.code for f in findings] == ["ATO-E001"]


def test_the_gate_does_not_apply_outside_a_contract_directory() -> None:
    assert validate.classification_gate("notes/system-context.md", None) == []
