"""The likelihood/consequence matrix, and the severity derived from it.

Severity is never stored on a risk. A rating typed into a file drifts the moment the
matrix changes or someone edits a likelihood and forgets the rest, and a register whose
ratings disagree with its own matrix is worse than one with no ratings at all.

The matrix itself is data, per assessment, so an organisation's own scales replace the
shipped placeholder without touching any code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

from . import frontmatter
from .repo import load_yaml

__all__ = ["Matrix", "MatrixError", "RatedRisk", "load", "rate_all"]


class MatrixError(RuntimeError):
    """The assessment has no usable risk matrix."""


class Matrix(NamedTuple):
    likelihood: tuple[str, ...]
    impact: tuple[str, ...]
    ratings: dict[str, dict[str, str]]
    severities: tuple[str, ...]
    review_required: bool

    def severity(self, likelihood: Any, impact: Any) -> str | None:
        """The rating for a pair, or ``None`` if the pair is not on the scales."""
        row = self.ratings.get(str(likelihood))
        if row is None:
            return None
        return row.get(str(impact))

    def rank(self, severity: str) -> int:
        """Where a severity sits on the configured scale. Unknown is -1.

        Callers must not use -1 as "least severe": an unrated risk is unfinished work, and
        `rate_all` sorts it above everything rated rather than below.
        """
        try:
            return self.severities.index(severity)
        except ValueError:
            return -1


class RatedRisk(NamedTuple):
    id: str
    title: str
    severity: str | None
    problem: str
    data: dict[str, Any]
    path: str


def load(root: Path | str) -> Matrix:
    document = load_yaml(Path(root) / "risk-matrix.yaml")
    if document is None:
        raise MatrixError(
            f"no readable risk-matrix.yaml in {root}. It is copied in by `ato init`; "
            "if it is missing, copy it from the plugin's config/."
        )
    ratings = {
        str(likelihood): {str(impact): str(rating) for impact, rating in row.items()}
        for likelihood, row in (document.get("ratings") or {}).items()
        if isinstance(row, dict)
    }
    return Matrix(
        likelihood=tuple(str(value) for value in document.get("likelihood") or ()),
        impact=tuple(str(value) for value in document.get("impact") or ()),
        ratings=ratings,
        severities=tuple(str(value) for value in document.get("severities") or ()),
        review_required=document.get("review-required") is True,
    )


def rate_all(root: Path | str) -> list[RatedRisk]:
    """Every risk in the assessment, rated, worst first.

    A risk whose likelihood or impact is not on the matrix's scales gets no severity and
    says why — silently rating it against a scale it does not use would be worse.
    """
    root = Path(root)
    matrix = load(root)
    rated: list[RatedRisk] = []
    for path in sorted((root / "risks").glob("RSK-*.md")):
        try:
            data, _ = frontmatter.parse(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        likelihood, impact = data.get("likelihood"), data.get("impact")
        severity = matrix.severity(likelihood, impact)
        problem = ""
        if severity is None and not (likelihood or impact):
            # A draft the assessor has not rated yet is not a defect; it is the normal
            # state of a risk between being drafted and being judged.
            problem = "has not been rated yet"
        elif severity is None:
            unknown = [
                str(value)
                for value, scale in ((likelihood, matrix.likelihood), (impact, matrix.impact))
                if str(value) not in scale
            ]
            problem = (
                f"{', '.join(unknown)} is not on the matrix scales"
                if unknown
                else f"the matrix has no rating for {likelihood}/{impact}"
            )
        rated.append(
            RatedRisk(
                id=str(data.get("id", path.stem)),
                title=str(data.get("title", "")),
                severity=severity,
                problem=problem,
                data=data,
                path=path.relative_to(root).as_posix(),
            )
        )
    # Unrated first, then rated worst-first. An unrated risk is outstanding work rather
    # than a low severity, and it has no defined position in a worst-first order — putting
    # it last makes the register imply it is the least severe, which is the one inference
    # it cannot support. A board reads top-down; unfinished business belongs there.
    return sorted(
        rated, key=lambda entry: (entry.severity is not None, -matrix.rank(entry.severity or ""))
    )
