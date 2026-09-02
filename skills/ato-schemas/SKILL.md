---
name: ato-schemas
description: >
  Use when writing or fixing a file in an ATO assessment's claims/, evidence/, controls/,
  risks/, rfi/ or sources/ directories, or when the contract hook has denied a write with
  an ATO-Exxx code and the fields or reference format need checking. Triggers: "ATO-E110",
  "ATO-E102", "what fields does a claim need", "why was my write denied", "the schema for
  a risk", writing any contract file by hand.
---

# The assessment file contract

Every file in a contract directory is markdown with YAML frontmatter. Frontmatter is facts and is validated; the body is prose and is not. An opinion belongs in the body under `## Assessor note`, or in `notes/`.

Run `ato validate .` to check the whole assessment at once.

## Naming

`<DIR>/<ID>-<slug>.md`, where the ID is `SRC|CLM|EVD|RSK|RFI` plus four digits — `claims/CLM-0042-privileged-access.md`. The filename carries the ID, which is how a reference resolves without an index. `ato next-id claims` gives you the next one.

Sources are a directory: `sources/SRC-0007-ssp-v2-4/index.md` holds the frontmatter, and the heading-split chunks sit beside it. Controls are keyed by framework: `controls/ism/ISM-0421.md`.

## References

References are by ID, never by path, so a rename never breaks one:

```yaml
source:
  - ref: SRC-0007#privileged-access
    locator: "p.34"
    quote: "All privileged access requires phishing-resistant MFA."
  - SRC-0011
```

`ref` is `SRC-NNNN` or `EVD-NNNN` with an optional `#anchor` matching a heading in the target. `locator` is free text for a human — page, line, section, timestamp. `quote` is verbatim.

Links point downward, toward evidence, and are never mirrored back: claim → source, evidence → claim, control → claim and evidence, risk → anything, RFI → what it resolves. Back-links are derived, never typed.

## Fields

| Type | Required | Notes |
|---|---|---|
| **source** | `id title kind received origin classification hash state updated` | `kind`: document, interview, scan-output, config-export, screenshot, correspondence, other. `state`: ingested, superseded |
| **claim** | `id title statement source state confidence method updated` | `state`: draft, asserted, corroborated, refuted, retired |
| **evidence** | `id title bears_on direction artifact method collected collected_by state updated` | `direction`: supports, refutes, mixed. `artifact` is a path — a blob cannot carry frontmatter |
| **control** | `id framework title status confidence method updated` | `status`: not-assessed, satisfied, partially-satisfied, not-satisfied, not-applicable, inherited |
| **risk** | `id title statement threat vulnerability consequence likelihood impact refs state updated` | `state`: draft, open, mitigating, accepted, closed. Severity is derived from `risk-matrix.yaml`, never stored |
| **rfi** | `id title question asked_of asked_on state updated` | `state`: open, answered, withdrawn, blocked |

`confidence` is low, medium or high. `method` is document-review, interview, observation, config-review, automated-scan or ad-hoc.

Conditionally required: a risk needs `owner` once it leaves `draft` and `disposition` once `accepted`; an RFI needs `answered_on` and `answer_source` once `answered`.

## Why a write gets denied

| Code | Meaning |
|---|---|
| `ATO-E001` | The assessment's classification is incomplete, or the marking is below the data or environment it describes |
| `ATO-E002` | A confined sub-agent tried to write outside `.ato/staging/`, or to use a shell. Extractors and evidence-checkers hand their findings to the caller; only the caller writes the assessment |
| `ATO-E003` | A contract write came from a sub-agent the hook could not identify. Hand the findings back and let the caller write them |
| `ATO-E101` | No frontmatter, or YAML outside the supported subset — the message names the line |
| `ATO-E102` | A required field is missing, including one required by another field's value |
| `ATO-E103` | A value is outside a closed enum |
| `ATO-E104` | An unknown field for this type |
| `ATO-E110` | Nothing cited. A claim needs `source`, evidence needs `bears_on`, a risk needs `refs`, an assessed control needs a claim or evidence |
| `ATO-E111` | A reference is not of the form `PREFIX-NNNN[#anchor]` |
| `ATO-E120` | `id` disagrees with the filename |
| `ATO-E121` | A control's `framework` disagrees with its directory |
| `ATO-E122` | The filename is not `<ID>-<slug>.md` |
| `ATO-E130` | Another file already uses this ID |
| `ATO-E140` | `method: ad-hoc` with `confidence: high` — degrading to ad-hoc handling caps confidence at medium |

The fix for `ATO-E110` is to find the reference, never to reword the entry.

## Warnings — these do not block a write

`ato validate .` reports these; the hook mentions them and lets the write through, because the thing they point at may be written moments later.

| Code | Meaning |
|---|---|
| `ATO-E112` | A reference points at something that does not exist yet |
| `ATO-E113` | An anchor matches no heading in the source it names |
| `ATO-E301` | A source no claim cites — nobody has read it, whatever the ingest log says |
| `ATO-E302` | An evidence entry whose artefact is not on disk |
| `ATO-E303` | A risk rated with a likelihood or consequence the matrix does not have (blocking) |
| `ATO-E304` | A control in a framework `assessment.yaml` does not list (blocking) |
| `ATO-E305` | A framework profile that selects no controls — nothing to assess against (blocking) |
| `ATO-E306` | A profile spelled unconventionally; it is understood, but write it canonically |
| `ATO-E307` | A claim names a staging artefact that is not on disk. Expected on a fresh clone — staging files are not committed |
| `ATO-E308` | A claim's quote is not in the staging artefact it says it came from. The statement is not checked — rewriting it in the assessment's voice is what a good claim looks like |
| `ATO-E309` | A source is cited by a claim while its classification is still the one ingest guessed at. Set `classification` and `classification_by: assessor` |

## The YAML subset

Block maps and sequences, inline `[a, b]` and `{a: b}`, quoted and bare scalars, `|` and `>` blocks, `#` comments, and typed scalars (int, float, `true`/`false`, `null`, `YYYY-MM-DD`). Not supported, and rejected with a line number: anchors and aliases, multiple documents, explicit tags, tab indentation, timestamps with a time part, and `yes`/`no`/`on`/`off` as booleans — quote those.

**Quote any value containing a colon followed by a space, or ending in one.** A control title is exactly where this bites:

```yaml
title: "AU-12: OpenShift auditing enabled by default"    # correct
title: AU-12: OpenShift auditing enabled by default      # rejected
```

Unquoted, that is not valid YAML — a real parser reads the second colon as starting a nested mapping and fails. `OFFICIAL:Sensitive` and `SRC-0007#anchor` are fine, because the colon there is not followed by a space.

The subset is deliberately no more permissive than YAML itself. A file this plugin accepts must be readable by any YAML tool, or the contract's promise that a conformant file is an integration is worth nothing.
