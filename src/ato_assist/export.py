"""The risk register and the report skeleton.

Both are generated and both are regenerable: nothing in `outputs/` is ever hand-edited,
because the moment it is, it disagrees with the files it came from. Both carry the
assessment's marking in their first line, because both leave the assessment.
"""

from __future__ import annotations

import csv
import datetime
from pathlib import Path
from typing import Any

from . import risk, xlsxlite
from .repo import load_assessment, load_yaml
from .session import PLUGIN_ROOT
from .status import summary

__all__ = ["ExportError", "register_csv", "register_xlsx", "report"]


class ExportError(RuntimeError):
    """The assessment cannot be exported as it stands."""


def register_rows(root: Path, today: datetime.date) -> list[list[str]]:
    """The register as a grid: marking line, headings, then one row per risk."""
    root = Path(root)
    columns = _columns(root)
    try:
        rated = risk.rate_all(root)
    except risk.MatrixError as exc:
        raise ExportError(str(exc)) from exc

    marking = _marking(root)
    rows = [[f"{marking} — risk register — {_system(root)} — {today.isoformat()}"]]
    rows.append([str(column.get("heading", column["field"])) for column in columns])
    for entry in rated:
        rows.append([_cell(entry, str(column["field"])) for column in columns])
    return rows


def register_csv(root: Path | str, today: datetime.date | None = None) -> Path:
    root = Path(root)
    today = today or datetime.date.today()
    path = root / "outputs" / f"{_short_name(root)}-risk-register.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(register_rows(root, today))
    return path


def register_xlsx(root: Path | str, today: datetime.date | None = None) -> Path:
    root = Path(root)
    today = today or datetime.date.today()
    path = root / "outputs" / f"{_short_name(root)}-risk-register.xlsx"
    return xlsxlite.write(path, register_rows(root, today), sheet_name="Risk register")


def report(root: Path | str, today: datetime.date | None = None) -> Path:
    """The report skeleton, with the numbers filled in and the prose left to the assessor."""
    root = Path(root)
    today = today or datetime.date.today()
    template = (PLUGIN_ROOT / "config" / "report-template.md").read_text(encoding="utf-8")
    assessment = load_assessment(root) or {}
    system = assessment.get("system") or {}
    scope = assessment.get("scope") or {}
    counts = summary(root, today)

    filled = template
    for key, value in {
        "marking": _marking(root),
        "system_name": _system(root),
        "system_owner": str(system.get("owner", "")) if isinstance(system, dict) else "",
        "assessor": str(system.get("assessor", "")) if isinstance(system, dict) else "",
        "period": f"to {today.isoformat()}",
        "frameworks": _frameworks(assessment),
        "scope_includes": _bullets(scope.get("includes") if isinstance(scope, dict) else []),
        "scope_excludes": _bullets(scope.get("excludes") if isinstance(scope, dict) else []),
        "control_summary": _control_summary(counts),
        "risk_summary": _risk_summary(root),
        "sources_table": _sources_table(root),
        "control_table": "See the control files under `controls/`.",
        "open_rfis": _open_rfis(counts),
    }.items():
        filled = filled.replace("{" + key + "}", value)

    path = root / "outputs" / f"{_short_name(root)}-report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"**{_marking(root)}**\n\n{filled}", encoding="utf-8")
    return path


# --- pieces -------------------------------------------------------------------------


def _columns(root: Path) -> list[dict[str, Any]]:
    document = load_yaml(root / "register-columns.yaml")
    if document is None:
        raise ExportError(
            f"no readable register-columns.yaml in {root}; it defines the register format"
        )
    columns = document.get("columns") or []
    return [column for column in columns if isinstance(column, dict) and column.get("field")]


def _cell(entry: risk.RatedRisk, field: str) -> str:
    if field == "severity":
        return entry.severity or f"unrated ({entry.problem})"
    value = entry.data.get(field, "")
    if isinstance(value, list):
        return ", ".join(
            str(item.get("ref") if isinstance(item, dict) else item) for item in value
        )
    return str(value)


def _marking(root: Path) -> str:
    classification = (load_assessment(root) or {}).get("classification") or {}
    if not isinstance(classification, dict):
        return "UNMARKED"
    return str(classification.get("marking", "UNMARKED"))


def _system(root: Path) -> str:
    system = (load_assessment(root) or {}).get("system") or {}
    return str(system.get("name", "the system")) if isinstance(system, dict) else "the system"


def _short_name(root: Path) -> str:
    system = (load_assessment(root) or {}).get("system") or {}
    return str(system.get("short_name", "assessment")) if isinstance(system, dict) else "assessment"


def _frameworks(assessment: dict[str, Any]) -> str:
    frameworks = assessment.get("frameworks") or []
    return ", ".join(
        f"{entry.get('id', '?')} {entry.get('profile', '')}".strip()
        for entry in frameworks
        if isinstance(entry, dict)
    )


def _bullets(values: Any) -> str:
    if not isinstance(values, list) or not values:
        return "_Not recorded._"
    return "\n".join(f"- {value}" for value in values)


def _control_summary(counts: dict[str, Any]) -> str:
    controls = counts.get("controls") or {}
    if not controls:
        return "_No controls have been assessed._"
    return "\n".join(f"- {status}: {count}" for status, count in sorted(controls.items()))


def _risk_summary(root: Path) -> str:
    try:
        rated = risk.rate_all(root)
    except risk.MatrixError:
        return "_No risk matrix is configured._"
    if not rated:
        return "_No risks have been raised._"
    return "\n".join(
        f"- **{entry.id}** ({entry.severity or 'unrated'}) — {entry.title}" for entry in rated
    )


def _sources_table(root: Path) -> str:
    from . import frontmatter

    lines = ["| ID | Document | Received | Classification |", "|----|----------|----------|----|"]
    for index in sorted((root / "sources").glob("SRC-*/index.md")):
        try:
            data, _ = frontmatter.parse(index.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        lines.append(
            f"| {data.get('id', '')} | {data.get('title', '')} | "
            f"{data.get('received', '')} | {data.get('classification', '')} |"
        )
    return "\n".join(lines) if len(lines) > 2 else "_No sources have been ingested._"


def _open_rfis(counts: dict[str, Any]) -> str:
    entries = counts.get("open_rfis") or []
    if not entries:
        return "_None outstanding._"
    return "\n".join(f"- {entry['id']} ({entry['age']}d) — {entry['title']}" for entry in entries)
