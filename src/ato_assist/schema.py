"""The file contract, as data.

These tables are the integration API. Anything — another plugin, a script, a human with
an editor — that writes a file matching them is integrated with the workbench, and the
PreToolUse hook rejects anything that does not.

Every field here is read by something. A field nothing reads is a field that drifts, so
it does not get to exist.
"""

from __future__ import annotations

from typing import NamedTuple

__all__ = [
    "AnyOfWhen",
    "CONFIDENCE",
    "Field",
    "ItemSchema",
    "MARKINGS",
    "METHOD",
    "RequiredWhen",
    "SCHEMAS",
    "marking_rank",
]

# Ordered lowest to highest. `classification.marking` must sit at or above both the data
# and the environment classification, which is a check rather than a convention.
MARKINGS = (
    "UNOFFICIAL",
    "OFFICIAL",
    "OFFICIAL:Sensitive",
    "PROTECTED",
    "SECRET",
    "TOP SECRET",
)

CONFIDENCE = ("low", "medium", "high")
METHOD = (
    "document-review",
    "interview",
    "observation",
    "config-review",
    "automated-scan",
    "ad-hoc",
)

# Any contract ID: a prefix and four digits. Control IDs are the framework's own
# (ISM-0421), which is why the prefix is not enumerated.
ANY_ID = r"[A-Z][A-Z0-9]*-\d{4}"


def marking_rank(marking: str) -> int:
    """Position on the classification scale, or -1 if it is not a known marking."""
    try:
        return MARKINGS.index(marking)
    except ValueError:
        return -1


class Field(NamedTuple):
    name: str
    kind: str = "str"  # str | int | date | str-list | path-list | id-list | ref-list | map
    required: bool = True
    enum: tuple[str, ...] | None = None
    ref_pattern: str | None = None  # for id-list and ref-list


class RequiredWhen(NamedTuple):
    """``field`` becomes required when ``when_field`` holds one of ``when_in``."""

    field: str
    when_field: str
    when_in: tuple[str, ...]


class AnyOfWhen(NamedTuple):
    """At least one of ``fields`` must be non-empty when the condition holds."""

    fields: tuple[str, ...]
    when_field: str
    message: str
    when_in: tuple[str, ...] = ()
    when_not_in: tuple[str, ...] = ()


class ItemSchema(NamedTuple):
    kind: str
    directory: str
    prefix: str | None  # None where the framework supplies the ID, as controls do
    fields: tuple[Field, ...]
    # Traceability fields: absent or empty is ATO-E110, not a plain missing-field error.
    min_one: tuple[str, ...] = ()
    required_when: tuple[RequiredWhen, ...] = ()
    any_of_when: tuple[AnyOfWhen, ...] = ()


_COMMON = (Field("updated", kind="date"),)

SOURCE = ItemSchema(
    kind="source",
    directory="sources",
    prefix="SRC",
    fields=(
        Field("id"),
        Field("title"),
        Field("kind", enum=("document", "interview", "scan-output", "config-export",
                            "screenshot", "correspondence", "other")),
        Field("received", kind="date"),
        Field("origin"),
        Field("classification", enum=MARKINGS),
        Field("hash"),
        Field("state", enum=("ingested", "superseded")),
        Field("artifact", kind="path-list", required=False),
        Field("anchors", kind="str-list", required=False),
        Field("method", enum=METHOD, required=False),
        Field("anchors_unavailable", kind="bool", required=False),
        Field("supersedes", kind="id-list", required=False, ref_pattern=r"SRC-\d{4}"),
        *_COMMON,
    ),
)

CLAIM = ItemSchema(
    kind="claim",
    directory="claims",
    prefix="CLM",
    fields=(
        Field("id"),
        Field("title"),
        Field("statement"),
        Field("source", kind="ref-list", ref_pattern=r"(?:SRC|EVD)-\d{4}"),
        Field("state", enum=("draft", "asserted", "corroborated", "refuted", "retired")),
        Field("confidence", enum=CONFIDENCE),
        Field("method", enum=METHOD),
        Field("tags", kind="str-list", required=False),
        # Provenance, not protection: where a claim came from an extractor's staging
        # file, naming it lets the sweep ask whether the claim corresponds to something
        # an extractor actually found. Optional, because a claim the caller wrote from
        # reading a section directly is equally legitimate.
        Field("derived_from", required=False),
        *_COMMON,
    ),
    min_one=("source",),
)

EVIDENCE = ItemSchema(
    kind="evidence",
    directory="evidence",
    prefix="EVD",
    fields=(
        Field("id"),
        Field("title"),
        Field("bears_on", kind="id-list", ref_pattern=r"CLM-\d{4}"),
        Field("direction", enum=("supports", "refutes", "mixed")),
        Field("artifact", kind="path-list"),
        Field("method", enum=METHOD),
        Field("collected", kind="date"),
        Field("collected_by"),
        Field("state", enum=("draft", "accepted", "superseded")),
        Field("integrity", required=False),
        *_COMMON,
    ),
    min_one=("bears_on", "artifact"),
)

CONTROL = ItemSchema(
    kind="control",
    directory="controls",
    prefix=None,
    fields=(
        Field("id"),
        Field("framework"),
        Field("title"),
        Field("status", enum=("not-assessed", "satisfied", "partially-satisfied",
                              "not-satisfied", "not-applicable", "inherited")),
        Field("claims", kind="id-list", required=False, ref_pattern=r"CLM-\d{4}"),
        Field("evidence", kind="id-list", required=False, ref_pattern=r"EVD-\d{4}"),
        Field("confidence", enum=CONFIDENCE),
        Field("method", enum=METHOD),
        *_COMMON,
    ),
    any_of_when=(
        AnyOfWhen(
            fields=("claims", "evidence"),
            when_field="status",
            when_not_in=("not-assessed",),
            message="an assessed control must cite at least one claim or evidence entry",
        ),
        AnyOfWhen(
            fields=("claims",),
            when_field="status",
            when_in=("not-applicable", "inherited"),
            message=(
                "scoping a control out or inheriting it is itself a judgement, so it must "
                "cite the claim that argues it"
            ),
        ),
    ),
)

RISK = ItemSchema(
    kind="risk",
    directory="risks",
    prefix="RSK",
    fields=(
        Field("id"),
        Field("title"),
        Field("statement"),
        Field("threat"),
        Field("vulnerability"),
        Field("consequence"),
        Field("likelihood"),  # enum comes from config/risk-matrix.yaml, checked repo-wide
        Field("impact"),
        Field("refs", kind="id-list", ref_pattern=ANY_ID),
        Field("state", enum=("draft", "open", "mitigating", "accepted", "closed")),
        Field("owner", required=False),
        Field("disposition", required=False),
        Field("treatment", required=False),
        *_COMMON,
    ),
    min_one=("refs",),
    required_when=(
        RequiredWhen("owner", "state", ("open", "mitigating", "accepted", "closed")),
        RequiredWhen("disposition", "state", ("accepted",)),
    ),
)

RFI = ItemSchema(
    kind="rfi",
    directory="rfi",
    prefix="RFI",
    fields=(
        Field("id"),
        Field("title"),
        Field("question"),
        Field("asked_of"),
        Field("asked_on", kind="date"),
        Field("due", kind="date", required=False),
        Field("state", enum=("open", "answered", "withdrawn", "blocked")),
        Field("answered_on", kind="date", required=False),
        Field("answer_source", kind="ref-list", required=False,
              ref_pattern=r"(?:SRC|EVD)-\d{4}"),
        Field("resolves", kind="id-list", required=False, ref_pattern=ANY_ID),
        *_COMMON,
    ),
    required_when=(
        RequiredWhen("answered_on", "state", ("answered",)),
        RequiredWhen("answer_source", "state", ("answered",)),
    ),
)

SCHEMAS = {s.directory: s for s in (SOURCE, CLAIM, EVIDENCE, CONTROL, RISK, RFI)}
