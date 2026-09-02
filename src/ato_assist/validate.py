"""The validator. One implementation, two callers.

The PreToolUse hook runs L1 (everything decidable from a document's own text) and L2
(referential checks needing a few globs). The CLI runs those plus L3, the repo-wide
sweep. Passing ``repo=None`` is what selects the hook's cheaper view.

Every finding carries a stable ``ATO-Exxx`` code. Codes are quoted in deny messages and
grepped by tests, so they are never renumbered.
"""

from __future__ import annotations

import contextlib
import re
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple

from . import frontmatter
from .miniyaml import MiniYamlError
from .schema import MARKINGS, SCHEMAS, AnyOfWhen, Field, ItemSchema, marking_rank

__all__ = [
    "Finding",
    "classification_gate",
    "schema_for_path",
    "validate_document",
    "validate_repo",
]

_SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_ANCHOR = r"(?:#[a-z0-9][a-z0-9-]*)?"
_HEADINGS = re.compile(r"^#{1,6}\s+(.+?)\s*#*$", re.MULTILINE)


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
    if parts[-1] == "README.md":
        # Every contract directory carries one, explaining what belongs in it.
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
    if repo is not None:
        findings += _check_references(schema, path, data, repo)
    return findings


# --- L2: checks that need to look at the rest of the repository ---------------------


def _check_references(
    schema: ItemSchema, path: str, data: dict[str, Any], repo: Any
) -> list[Finding]:
    """Resolve what this document points at, and check nothing else already owns its ID.

    A dangling reference only warns: the target may be written later in the same turn, and
    denying that would make the workbench hostile enough that someone turns the hook off —
    which costs far more than a dangling ref. A colliding ID denies, because the filename
    carries the ID and two files claiming one make every reference to it ambiguous.
    """
    findings: list[Finding] = []
    existing = repo.items.get(str(data.get("id")))
    if existing is not None and existing.path != path:
        findings.append(_error(
            "ATO-E130", path, "id",
            f"{data.get('id')} is already {existing.path}",
            hint="the filename carries the ID; two files cannot share one",
        ))

    for field in schema.fields:
        if field.kind not in ("ref-list", "id-list"):
            continue
        for entry in data.get(field.name) or []:
            ref = entry.get("ref") if isinstance(entry, dict) else entry
            if not isinstance(ref, str):
                continue
            target, _, anchor = ref.partition("#")
            item = repo.items.get(target)
            if item is None:
                findings.append(_warn(
                    "ATO-E112", path, field.name,
                    f"{target} does not exist yet",
                    hint="write it, or correct the reference",
                ))
            elif anchor and not _anchor_exists(repo, item, anchor):
                findings.append(_warn(
                    "ATO-E113", path, field.name,
                    f"{target} has no section {anchor!r}",
                    hint="anchors match a heading in the source, slugified",
                ))
    return findings


def _anchor_exists(repo: Any, item: Any, anchor: str) -> bool:
    """An anchor matches a heading in the target, or an anchor it declares outright."""
    if anchor in {str(value) for value in item.data.get("anchors") or []}:
        return True
    directory = (repo.root / item.path).parent
    for candidate in directory.glob("*.md"):
        try:
            text = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(_slugify(heading) == anchor for heading in _HEADINGS.findall(text)):
            return True
    return False


def _slugify(heading: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")


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


# --- L3: the repo-wide sweep --------------------------------------------------------


def validate_repo(root: Path | str, today: Any = None) -> list[Finding]:
    """Validate a whole assessment: every document, plus what only the whole tells you."""
    from .repo import RepoIndex  # imported here: the hook never needs the index
    from .risk import MatrixError
    from .risk import load as load_matrix

    root = Path(root)
    index = RepoIndex(root)
    findings: list[Finding] = []

    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root).as_posix()
        if schema_for_path(relative) is None:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(_error("ATO-E100", relative, None, f"unreadable: {exc}"))
            continue
        findings += validate_document(relative, text, index)

    findings += _sweep_orphans(index)
    findings += _sweep_artifacts(index)
    # A missing matrix is reported where it bites, by the exporter; here it just means
    # ratings cannot be checked.
    with contextlib.suppress(MatrixError):
        findings += _sweep_ratings(index, load_matrix(root))
    findings += _sweep_frameworks(index)
    findings += _sweep_profiles(index)
    findings += _sweep_derivations(index)
    _ = today
    return findings


def _sweep_orphans(index: Any) -> list[Finding]:
    """A source nothing cites has been read by nobody, whatever the ingest log says."""
    cited = {
        target.split("#", 1)[0]
        for item in index.of_kind("claims")
        for target in index.refs_of(item, "source")
    }
    return [
        _warn("ATO-E301", item.path, None,
              f"{item.id} is cited by no claim",
              hint="extract its claims, or mark it superseded")
        for item in index.of_kind("sources")
        if item.id not in cited and item.data.get("state") != "superseded"
    ]


def _sweep_artifacts(index: Any) -> list[Finding]:
    findings: list[Finding] = []
    for item in index.of_kind("evidence"):
        for artifact in item.data.get("artifact") or []:
            if not (index.root / str(artifact)).exists():
                findings.append(_warn(
                    "ATO-E302", item.path, "artifact",
                    f"{artifact} is not on disk",
                    hint="evidence that points at nothing cannot be reviewed",
                ))
    return findings


def _sweep_ratings(index: Any, matrix: Any) -> list[Finding]:
    findings: list[Finding] = []
    for item in index.of_kind("risks"):
        likelihood, impact = item.data.get("likelihood"), item.data.get("impact")
        if matrix.severity(likelihood, impact) is None:
            findings.append(_error(
                "ATO-E303", item.path, "likelihood",
                f"{likelihood}/{impact} is not on the matrix scales",
                hint="use the scales in risk-matrix.yaml, or change the matrix",
            ))
    return findings


def _sweep_frameworks(index: Any) -> list[Finding]:
    configured = {
        str(entry.get("id"))
        for entry in index.assessment.get("frameworks") or []
        if isinstance(entry, dict)
    }
    if not configured:
        return []
    return [
        _error("ATO-E304", item.path, "framework",
               f"{item.data.get('framework')} is not a framework in assessment.yaml "
               f"({', '.join(sorted(configured))})")
        for item in index.of_kind("controls")
        if str(item.data.get("framework")) not in configured
    ]


def _sweep_derivations(index: Any) -> list[Finding]:
    """Check a claim against the staging artefact it says it came from.

    This is provenance, not protection. Nothing stops a claim being written without a
    derivation, and anyone who can fabricate a claim can fabricate a staging file. What
    it buys is a question a script can answer — "does this claim correspond to something
    an extractor found" — where "who wrote this" is a question no hook can answer at all.

    Staging files are working artefacts and are not committed, so a missing one warns
    rather than blocks: on a fresh clone every derivation is unresolvable, and that is
    expected rather than wrong.
    """
    findings: list[Finding] = []
    for item in index.of_kind("claims"):
        derivation = item.data.get("derived_from")
        if not isinstance(derivation, str) or not derivation:
            continue
        artefact = index.root / derivation
        if not artefact.is_file():
            findings.append(_warn(
                "ATO-E307", item.path, "derived_from",
                f"{derivation} is not on disk",
                hint="staging files are working artefacts and are not committed; this is "
                     "expected on a fresh clone",
            ))
            continue
        try:
            text = artefact.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # Check the quote, never the statement. A statement rewritten in the assessment's
        # own voice is what a well-made claim looks like; matching on it would warn on
        # careful work and stay silent on a candidate copied across verbatim. The quote is
        # the one thing that must survive unchanged from document to staging to claim.
        quotes = [
            entry["quote"].strip()
            for entry in item.data.get("source") or []
            if isinstance(entry, dict) and isinstance(entry.get("quote"), str)
        ]
        missing = [quote for quote in quotes if quote and quote not in text]
        if missing:
            findings.append(_warn(
                "ATO-E308", item.path, "derived_from",
                f"{item.id} quotes {missing[0][:60]!r}, which is not in {derivation}",
                hint="either the quote was edited after extraction, or the claim did not "
                     "come from there",
            ))
    return findings


def _sweep_profiles(index: Any) -> list[Finding]:
    """A framework profile that selects no controls means there is nothing to assess against.

    This is blocking rather than a warning because the symptom appears late — an
    assessment can be scaffolded, pass every other check and be worked on for weeks
    before control mapping finds nothing to map onto.
    """
    from .oscal import CatalogueError, normalise_profile
    from .oscal import load as load_catalogue

    findings: list[Finding] = []
    for entry in index.assessment.get("frameworks") or []:
        if not isinstance(entry, dict) or entry.get("id") != "ism":
            continue  # only frameworks the plugin ships a catalogue for can be checked
        stated = entry.get("profile")
        profile = normalise_profile(stated)
        try:
            catalogue = load_catalogue()
        except CatalogueError:
            return findings
        if profile is None or not catalogue.profile(profile):
            findings.append(_error(
                "ATO-E305", "assessment.yaml", "frameworks",
                f"profile {stated!r} selects no {str(entry.get('id')).upper()} controls",
                hint="profiles are: " + ", ".join(catalogue.profiles),
            ))
        elif profile != stated:
            findings.append(_warn(
                "ATO-E306", "assessment.yaml", "frameworks",
                f"profile {stated!r} is understood as {profile!r}; write it that way",
                hint="the spelling is tolerated on the way in, but not everywhere is "
                     "guaranteed to normalise it",
            ))
    return findings


def _warn(code: str, path: str, field: str | None, message: str, hint: str = "") -> Finding:
    return Finding("warn", code, path, field, message, hint)
