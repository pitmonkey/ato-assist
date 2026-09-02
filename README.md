# ato-assist

A Claude Code plugin that helps a security assessor run an ATO (authority to operate) security risk assessment.

It is a **workbench, not an oracle**. It does not one-shot an assessment. It structures the assessor's working directory, runs discrete workflow steps on request, enforces traceability mechanically, and derives status from files. The assessor owns all judgement; the plugin owns the workflow and the data contract.

## Install

```
/plugin marketplace add pitmonkey/ato-assist
/plugin install ato-assist@ato-assist
```

Nothing else to install: the plugin runs against system `python3` with no dependencies and no virtualenv.

Optional external binaries, used when present and degraded around when absent: `pandoc` (docx), `poppler-utils` for `pdftotext` (PDF).

## Use

Run `/ato-init` in an empty directory to scaffold an assessment. `/ato-status` tells you where you are at any time.

| Skill | Purpose |
|---|---|
| `/ato-init` | Scaffold the assessment repo and capture classification |
| `/ato-interview` | Structured interview about the system, before ingest |
| `/ato-ingest` | Process `inbox/` into `sources/` with a hash manifest and acronym scan |
| `/ato-glossary` | Resolve queued acronyms one at a time |
| `/ato-extract-claims` | SSP sections into discrete sourced claims |
| `/ato-map-controls` | Claims to ISM controls, using the ISM OSCAL catalogue as data |
| `/ato-reconcile-evidence` | Does the evidence support each claim? |
| `/ato-risk` | Draft a risk with enforced structure and the configured matrix |
| `/ato-challenge` | Adversarial review of the whole assessment |
| `/ato-rfi` | Create, list and export requests for information |
| `/ato-phase` | Show exit criteria; move the phase marker |
| `/ato-status` | Derived status, one screen |
| `/ato-export` | Risk register and report skeleton |
| `/ato-schemas` | The file contract, and what each `ATO-Exxx` denial means |

## The `ato` CLI

Skills call it; so can you. `ato --help` lists everything.

```
ato init      scaffold an assessment          ato controls  read the ISM catalogue
ato ingest    inbox/ -> sources/              ato risk      scales, and risks rated
ato status    where things stand              ato evidence  record an artefact
ato validate  check against the contract      ato rfi       raise, close, list, export
ato phase     move the marker                 ato export    register and report
ato next-id   the next free ID                ato commit    a structured commit
```

## The file contract

Every artefact is markdown with YAML frontmatter, hand-editable and machine-checkable. Claims, controls and risks must cite a source; a `PreToolUse` hook denies writes that do not. See `CLAUDE.md` and `skills/ato-schemas/SKILL.md` for the schemas.

Integrating a new evidence source means writing a conformant file into `evidence/` — nothing more. Domain-specific evidence analysis belongs in separate small adapter plugins, not here.

## Status

Early. Placeholder configuration ships marked `review-required: true` (risk matrix, phase sequence, register columns, report template); `ato status` nags until an assessment team has validated them.

The second reference adapter is deliberately unwritten — it waits on the assessment team naming their most common evidence source.

## Licence

MIT. The vendored ISM OSCAL content under `data/ism-oscal/` is © Commonwealth of Australia, licensed CC BY 4.0.
