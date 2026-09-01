"""The validator. One implementation, two callers.

The PreToolUse hook runs L1 (everything decidable from a document's own text) and L2
(referential checks needing a few globs). The CLI runs those plus L3, the repo-wide
sweep. Passing ``repo=None`` is what selects the hook's cheaper view.

Every finding carries a stable ``ATO-Exxx`` code. Codes are quoted in deny messages and
grepped by tests, so they are never renumbered.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, NamedTuple

from . import frontmatter
from .miniyaml import MiniYamlError
from .schema import MARKINGS, SCHEMAS, AnyOfWhen, Field, ItemSchema, marking_rank

__all__ = ["Finding", "classification_gate", "schema_for_path", "validate_document"]

_SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_ANCHOR = r"(?:#[a-z0-9][a-z0-9-]*)?"


class Finding(NamedTuple):
    level: str  # "error" denies; "warn" nudges
    code: str
    path: str
    field: str | None
    message: str
    hint: str = ""


def schema_for_path(path: str) -> tuple[ItemSchema, str] | None:
    """The schema governing ``path``, and the name carrying its ID.

    Returns ``None`` for anything the contract does not govern — notes, glossary,
    outputs, and the heading-split chunk files inside a source directory.
    """
    parts = PurePosixPath(path).parts
    if not parts:
        return None
    directory = parts[0]
    schema = SCHEMAS.get(directory)
    if schema is None:
        return None
    if directory == "sources":
        # Only the index carries frontmatter; the chunks beside it are extracted prose.
        if len(parts) == 3 and parts[2] == "index.md":
            return schema, parts[1]
        return None
    if directory == "controls":
        return (schema, parts[2]) if len(parts) == 3 else None
    return (schema, parts[1]) if len(parts) == 2 else None


def validate_document(path: str, text: str, repo: Any | None = None) -> list[Finding]:
    """Validate one document's text. ``repo`` enables the referential checks."""
    resolved = schema_for_path(path)
    if resolved is None:
        return []
    schema, id_holder = resolved

    try:
        data, _ = frontmatter.parse(text)
    except frontmatter.MissingFrontmatterError:
        return [_error("ATO-E101", path, None, "no YAML frontmatter block",
                       hint="every file in a contract directory starts with a --- block")]
    except MiniYamlError as exc:
        return [_error("ATO-E101", path, None, f"unparseable frontmatter: {exc}",
                       hint="see the supported YAML subset in skills/ato-schemas")]

    findings: list[Finding] = []
    findings += _check_naming(schema, path, id_holder, data)
    findings += _check_fields(schema, path, data)
    findings += _check_conditionals(schema, path, data)
    findings += _check_traceability(schema, path, data)
    findings += _check_degradation(schema, path, data)
    _ = repo  # referential checks land in the next layer
    return findings


# --- naming -----------------------------------------------------------------------


def _check_naming(
    schema: ItemSchema, path: str, id_holder: str, data: dict[str, Any]
) -> list[Finding]:
    findings: list[Finding] = []
    declared = data.get("id")

    if schema.prefix is not None:
        convention = (
            rf"^{schema.prefix}-\d{{4}}-{_SLUG}$"
            if schema.directory == "sources"
            else rf"^{schema.prefix}-\d{{4}}-{_SLUG}\.md$"
        )
        if not re.match(convention, id_holder):
            noun = "directory" if schema.directory == "sources" else "file"
            findings.append(_error(
                "ATO-E122", path, None,
                f"{noun} name {id_holder!r} is not <{schema.prefix}-NNNN>-<slug>",
                hint="the name carries the ID, which is how a reference resolves",
            ))
        expected = "-".join(id_holder.split("-")[:2])
    else:
        expected = PurePosixPath(id_holder).stem

    if isinstance(declared, str) and declared != expected:
        findings.append(_error(
            "ATO-E120", path, "id",
            f"id {declared!r} disagrees with the name, which says {expected!r}",
        ))

    if schema.directory == "controls":
        framework = PurePosixPath(path).parts[1]
        if data.get("framework") != framework:
            findings.append(_error(
                "ATO-E121", path, "framework",
                f"framework {data.get('framework')!r} disagrees with the directory "
                f"{framework!r}",
            ))
    return findings


# --- fields -----------------------------------------------------------------------


def _check_fields(schema: ItemSchema, path: str, data: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    known = {field.name for field in schema.fields}
    for name in data:
        if name not in known:
            findings.append(_error(
                "ATO-E104", path, name,
                f"unknown field {name!r} for a {schema.kind}",
                hint=f"known fields: {', '.join(sorted(known))}",
            ))
    for field in schema.fields:
        if field.name in schema.min_one:
            continue  # traceability fields report as ATO-E110 instead
        value = data.get(field.name)
        if value is None:
            if field.required:
                findings.append(_error(
                    "ATO-E102", path, field.name, f"field {field.name!r} is required"
                ))
            continue
        findings += _check_value(field, path, value)
    return findings


def _check_value(field: Field, path: str, value: Any) -> list[Finding]:
    if field.enum and value not in field.enum:
        return [_error(
            "ATO-E103", path, field.name,
            f"{value!r} is not one of: {', '.join(field.enum)}",
        )]
    if field.kind.endswith("-list"):
        if not isinstance(value, list):
            return [_error("ATO-E103", path, field.name, "expected a list")]
        return _check_list(field, path, value)
    return []


def _check_list(field: Field, path: str, items: list[Any]) -> list[Finding]:
    if field.ref_pattern is None:
        return []
    pattern = re.compile(rf"^(?:{field.ref_pattern}){_ANCHOR}$")
    findings: list[Finding] = []
    for item in items:
        ref = item.get("ref") if isinstance(item, dict) else item
        if not isinstance(ref, str) or not pattern.match(ref):
            findings.append(_error(
                "ATO-E111", path, field.name,
                f"{ref!r} is not a reference of the form {field.ref_pattern}[#anchor]",
                hint="references are by ID so they survive a rename",
            ))
    return findings


# --- conditionals and traceability -------------------------------------------------


def _check_conditionals(
    schema: ItemSchema, path: str, data: dict[str, Any]
) -> list[Finding]:
    findings: list[Finding] = []
    for rule in schema.required_when:
        if data.get(rule.when_field) in rule.when_in and not data.get(rule.field):
            findings.append(_error(
                "ATO-E102", path, rule.field,
                f"field {rule.field!r} is required when {rule.when_field} is "
                f"{data.get(rule.when_field)!r}",
            ))
    return findings


def _check_traceability(
    schema: ItemSchema, path: str, data: dict[str, Any]
) -> list[Finding]:
    findings: list[Finding] = []
    for name in schema.min_one:
        if not data.get(name):
            findings.append(_error(
                "ATO-E110", path, name,
                f"field {name!r} is required and must have at least one entry",
                hint="a claim, control or risk with no source is not assessable",
            ))
        else:
            field = next(f for f in schema.fields if f.name == name)
            findings += _check_value(field, path, data[name])
    findings += _check_any_of(schema.any_of_when, path, data)
    return findings


def _check_any_of(
    rules: tuple[AnyOfWhen, ...], path: str, data: dict[str, Any]
) -> list[Finding]:
    findings: list[Finding] = []
    for rule in rules:
        actual = data.get(rule.when_field)
        applies = (actual in rule.when_in) if rule.when_in else (actual not in rule.when_not_in)
        if applies and not any(data.get(name) for name in rule.fields):
            findings.append(_error("ATO-E110", path, rule.fields[0], rule.message))
    return findings


def _check_degradation(
    schema: ItemSchema, path: str, data: dict[str, Any]
) -> list[Finding]:
    """Degrading to ad-hoc handling is always allowed; claiming high confidence in it is not."""
    _ = schema
    if data.get("method") == "ad-hoc" and data.get("confidence") == "high":
        return [_error(
            "ATO-E140", path, "confidence",
            "ad-hoc handling caps confidence at medium",
            hint="log the missing adapter in tooling-gaps.md",
        )]
    return []


def _error(code: str, path: str, field: str | None, message: str, hint: str = "") -> Finding:
    return Finding("error", code, path, field, message, hint)


# --- the classification gate --------------------------------------------------------


_CLASSIFICATION_FIELDS = ("data", "environment", "marking")


def classification_gate(path: str, assessment: dict[str, Any] | None) -> list[Finding]:
    """Refuse to let assessment content exist before it is known how to mark it.

    An assessor who starts extracting claims before the classification is settled ends up
    with a repository nobody can safely file, so this is a deny and not a nudge. It only
    applies to the contract directories; notes and scratch work are unaffected.
    """
    if schema_for_path(path) is None:
        return []
    if assessment is None:
        return [_error(
            "ATO-E001", path, None,
            "assessment.yaml is missing or unreadable, so the classification is unknown",
            hint="run /ato-init, or fix the YAML it reports",
        )]

    classification = assessment.get("classification") or {}
    missing = [name for name in _CLASSIFICATION_FIELDS if not classification.get(name)]
    if missing:
        return [_error(
            "ATO-E001", path, "classification",
            f"assessment.yaml is missing classification.{', classification.'.join(missing)}",
            hint="all three are required: data, environment, and the marking artefacts carry",
        )]

    ranks = {name: marking_rank(str(classification[name])) for name in _CLASSIFICATION_FIELDS}
    off_scale = [name for name, rank in ranks.items() if rank < 0]
    if off_scale:
        return [_error(
            "ATO-E001", path, "classification",
            f"classification.{off_scale[0]} is {classification[off_scale[0]]!r}, "
            f"which is not a known marking",
        )]

    highest = max(ranks["data"], ranks["environment"])
    if ranks["marking"] < highest:
        return [_error(
            "ATO-E001", path, "classification",
            f"marking {classification['marking']!r} is below "
            f"{MARKINGS[highest]!r}, which this system already handles",
            hint="artefacts inherit the highest classification they describe",
        )]
    return []
