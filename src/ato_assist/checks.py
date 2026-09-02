"""The exit-criteria vocabulary.

Five verbs, all decidable by a script against the files. That limit is the point: a
criterion that needs more than these is not machine-evaluable, and pretending otherwise
produces a phase gate that quietly means nothing. Such a criterion belongs in
`decisions.md` as a human sign-off instead.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import Any, NamedTuple

from .repo import Item, RepoIndex

__all__ = ["CheckResult", "evaluate", "evaluate_phase"]


class CheckResult(NamedTuple):
    """The outcome of one criterion.

    ``applicable`` is false when the criterion constrains a collection that is still
    empty. "No claim is still a draft" is trivially true before any claim exists, and
    counting that as met makes a phase read two-thirds complete before any work has been
    done — then go backwards as real drafts appear. A criterion that cannot yet say
    anything is reported as such and left out of the fraction.
    """

    criterion_id: str
    check: str
    passed: bool
    actual: str
    expected: str
    offenders: list[str]
    describe: str = ""
    applicable: bool = True


_Check = Callable[..., CheckResult]
CHECKS: dict[str, _Check] = {}


def check(name: str) -> Callable[[_Check], _Check]:
    def register(function: _Check) -> _Check:
        CHECKS[name] = function
        return function

    return register


def evaluate(
    index: RepoIndex, criterion: dict[str, Any], today: datetime.date
) -> CheckResult:
    """Run one criterion. A broken criterion fails; it never raises."""
    criterion_id = str(criterion.get("id", "?"))
    name = str(criterion.get("check"))
    describe = str(criterion.get("describe", ""))
    function = CHECKS.get(name)
    if function is None:
        return CheckResult(criterion_id, name, False, "unknown check", "a known check", [],
                           describe)
    args = dict(criterion.get("args") or {})
    try:
        result = function(index, criterion_id=criterion_id, today=today, **args)
    except Exception as exc:  # a malformed process.yaml must not take out /status
        return CheckResult(criterion_id, name, False, f"error: {exc}", "evaluable", [],
                           describe)
    return result._replace(describe=describe)


def evaluate_phase(
    index: RepoIndex, phase_id: str, today: datetime.date
) -> list[CheckResult]:
    """Every exit criterion of a phase, in the order `process.yaml` lists them."""
    for phase in index.process().get("phases") or []:
        if isinstance(phase, dict) and phase.get("id") == phase_id:
            return [
                evaluate(index, criterion, today)
                for criterion in phase.get("exit_criteria") or []
            ]
    return []


def _matching(items: list[Item], where: dict[str, Any] | None) -> list[Item]:
    """Filter items by frontmatter fields. A list of values means any one of them."""
    if not where:
        return items
    return [
        item
        for item in items
        if all(_holds(item.data.get(field), wanted) for field, wanted in where.items())
    ]


def _holds(value: Any, wanted: Any) -> bool:
    return value in wanted if isinstance(wanted, list) else value == wanted


@check("field_count")
def _field_count(
    index: RepoIndex,
    *,
    criterion_id: str,
    dir: str,  # noqa: A002 - the criterion vocabulary says "dir"
    field: str,
    equals: Any = None,
    max: int | None = None,  # noqa: A002
    min: int | None = None,  # noqa: A002
    **_: Any,
) -> CheckResult:
    """Count the items in a directory matching a value, and assert a bound on that count."""
    matched = [
        item
        for item in index.of_kind(dir)
        if (item.data.get(field) == equals if equals is not None else bool(item.data.get(field)))
    ]
    passed = True
    expected = "any"
    if max is not None:
        passed = passed and len(matched) <= int(max)
        expected = f"at most {max}"
    if min is not None:
        passed = passed and len(matched) >= int(min)
        expected = f"at least {min}"
    offenders = [item.path for item in matched] if max is not None else []
    # A ceiling says nothing about an empty collection; a floor is a real claim about one.
    applicable = min is not None or bool(index.of_kind(dir))
    return CheckResult(
        criterion_id, "field_count", passed, str(len(matched)), expected, offenders,
        applicable=applicable,
    )


@check("no_orphans")
def _no_orphans(
    index: RepoIndex,
    *,
    criterion_id: str,
    referenced_by: str,
    via: str,
    where: dict[str, Any] | None = None,
    **kwargs: Any,
) -> CheckResult:
    """Every item in one directory is pointed at by something in another."""
    origin = kwargs["from"]
    referenced = {
        target
        for item in index.of_kind(referenced_by)
        for target in RepoIndex.refs_of(item, via)
    }
    subject = _matching(index.of_kind(origin), where)
    offenders = [item.path for item in subject if item.id not in referenced]
    return CheckResult(
        criterion_id,
        "no_orphans",
        not offenders,
        f"{len(offenders)} uncited",
        "0 uncited",
        offenders,
        applicable=bool(subject),
    )


@check("required_ref")
def _required_ref(
    index: RepoIndex,
    *,
    criterion_id: str,
    dir: str,  # noqa: A002
    field: str,
    min: int = 1,  # noqa: A002
    where: dict[str, Any] | None = None,
    **_: Any,
) -> CheckResult:
    """Every item that the filter selects cites at least `min` things in a field."""
    subject = _matching(index.of_kind(dir), where)
    offenders = [
        item.path for item in subject if len(RepoIndex.refs_of(item, field)) < int(min)
    ]
    return CheckResult(
        criterion_id,
        "required_ref",
        not offenders,
        f"{len(offenders)} citing fewer than {min}",
        f"every item citing at least {min}",
        offenders,
        applicable=bool(subject),
    )


@check("age_max")
def _age_max(
    index: RepoIndex,
    *,
    criterion_id: str,
    today: datetime.date,
    dir: str,  # noqa: A002
    date_field: str,
    max_days: int,
    where: dict[str, Any] | None = None,
    **_: Any,
) -> CheckResult:
    """Nothing the filter selects is older than `max_days`."""
    offenders: list[str] = []
    oldest = 0
    subject = _matching(index.of_kind(dir), where)
    for item in subject:
        when = item.data.get(date_field)
        if not isinstance(when, datetime.date):
            continue
        age = (today - when).days
        oldest = max(oldest, age)
        if age > int(max_days):
            offenders.append(item.path)
    return CheckResult(
        criterion_id,
        "age_max",
        not offenders,
        f"oldest {oldest}d",
        f"at most {max_days}d",
        offenders,
        applicable=bool(subject),
    )


@check("file_exists")
def _file_exists(
    index: RepoIndex, *, criterion_id: str, path: str, **_: Any
) -> CheckResult:
    """A named file exists and has something in it."""
    resolved = path.format(short_name=index.short_name())
    matches = [
        candidate
        for candidate in index.root.glob(resolved)
        if candidate.is_file() and candidate.stat().st_size > 0
    ]
    return CheckResult(
        criterion_id,
        "file_exists",
        bool(matches),
        "present" if matches else "missing",
        f"{resolved} present",
        [] if matches else [resolved],
    )
