"""export — the register and report, regenerable and marked."""

from __future__ import annotations

import csv
import datetime
import zipfile
from pathlib import Path

import pytest

from ato_assist import export, frontmatter, scaffold
from tests_support import SPEC

TODAY = datetime.date(2026, 9, 2)


@pytest.fixture
def assessment(tmp_path: Path) -> Path:
    scaffold.create(tmp_path, SPEC)
    _risk(tmp_path, 1, "almost-certain", "severe", title="Unmonitored privileged access")
    _risk(tmp_path, 2, "rare", "minor", title="Stale documentation")
    return tmp_path


def _risk(root: Path, number: int, likelihood: str, impact: str, **overrides: object) -> None:
    fields: dict[str, object] = {
        "id": f"RSK-{number:04d}",
        "title": "A risk",
        "statement": "Something could happen.",
        "threat": "An insider",
        "vulnerability": "No session logging",
        "consequence": "Undetected exfiltration",
        "likelihood": likelihood,
        "impact": impact,
        "refs": ["ISM-0421", "CLM-0042"],
        "state": "open",
        "owner": "System owner",
        "updated": TODAY,
    }
    fields.update(overrides)
    (root / "risks" / f"RSK-{number:04d}-r.md").write_text(
        frontmatter.render(fields, "Body.\n")
    )


def test_the_register_uses_the_configured_columns(assessment: Path) -> None:
    path = export.register_csv(assessment, TODAY)
    rows = list(csv.reader(path.read_text().splitlines()))
    assert rows[0][0].startswith("PROTECTED")  # the marking leads the file
    assert rows[1][:2] == ["Risk ID", "Risk"]


def test_the_register_carries_the_derived_severity(assessment: Path) -> None:
    path = export.register_csv(assessment, TODAY)
    rows = list(csv.reader(path.read_text().splitlines()))
    headings = rows[1]
    body = rows[2]
    assert body[headings.index("Risk rating")] == "extreme"


def test_the_register_is_worst_first(assessment: Path) -> None:
    path = export.register_csv(assessment, TODAY)
    rows = list(csv.reader(path.read_text().splitlines()))[2:]
    assert [row[0] for row in rows] == ["RSK-0001", "RSK-0002"]


def test_references_are_rendered_so_a_spreadsheet_can_show_them(assessment: Path) -> None:
    path = export.register_csv(assessment, TODAY)
    assert "ISM-0421, CLM-0042" in path.read_text()


def test_the_register_is_named_for_the_system(assessment: Path) -> None:
    assert export.register_csv(assessment, TODAY).name == "exs-risk-register.csv"


def test_the_xlsx_register_is_a_real_workbook(assessment: Path) -> None:
    path = export.register_xlsx(assessment, TODAY)
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        assert "xl/worksheets/sheet1.xml" in names
        sheet = archive.read("xl/worksheets/sheet1.xml").decode()
    assert "Unmonitored privileged access" in sheet
    assert "PROTECTED" in sheet


def test_a_value_with_markup_characters_survives_the_xlsx(assessment: Path) -> None:
    _risk(assessment, 3, "rare", "minor", title="Ampersands & <angle brackets>")
    path = export.register_xlsx(assessment, TODAY)
    with zipfile.ZipFile(path) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode()
    assert "&amp;" in sheet
    assert "<angle" not in sheet


def test_the_report_skeleton_is_stamped_with_the_marking(assessment: Path) -> None:
    path = export.report(assessment, TODAY)
    text = path.read_text()
    assert text.splitlines()[0].strip() == "**PROTECTED**"
    assert "Example System" in text
    assert "{system_name}" not in text


def test_the_report_carries_the_numbers_rather_than_placeholders(assessment: Path) -> None:
    text = export.report(assessment, TODAY).read_text()
    assert "RSK-0001" in text
    assert "{risk_summary}" not in text


def test_exporting_without_a_matrix_is_refused_not_guessed(tmp_path: Path) -> None:
    scaffold.create(tmp_path, SPEC)
    (tmp_path / "risk-matrix.yaml").unlink()
    with pytest.raises(export.ExportError):
        export.register_csv(tmp_path, TODAY)
