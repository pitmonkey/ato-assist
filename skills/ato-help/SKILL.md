---
name: ato-help
description: >
  Use when someone is new to the ato-assist plugin and needs to know what it is, what is in it, and where to start — including outside or before any particular assessment step. Triggers: "/ato-help", "what does this plugin do", "what is ato-assist", "what skills are there", "how do I use this", "where do I start", "what can you do here", "I have just installed this", "list the ato skills". For where a live assessment stands use ato-status; for how an ATO assessment is conducted phase by phase, ato-process; for the fields a contract file needs, ato-schemas.
---

# ato-assist

What the plugin is, and everything in it.

## What this is

A workbench for an ATO (authority to operate) security risk assessment, not an oracle. It does not one-shot an assessment. It turns an empty directory into a repository where every claim traces to the page it came from, and it keeps the mechanics honest so the assessor can spend their attention on judgement.

The plugin owns the directory layout, the file schemas and the workflow. The assessor owns every judgement — whether a claim is met, whether a control is satisfied, what a risk rates, when a phase is done.

## Where to start

- In an empty directory, `/ato-init` scaffolds the assessment and captures the classification. It runs once, before anything else.
- In an assessment that already exists, `/ato-status` first. It is the only account of where things stand, and it is recomputed from the files every time it runs.

## The skills

**Start**

| Skill | Purpose |
| --- | --- |
| `/ato-init` | Scaffold the assessment repo and capture the three classifications |
| `/ato-interview` | Structured interview about the system, before any document colours it |

**Material in**

| Skill | Purpose |
| --- | --- |
| `/ato-ingest` | Process `inbox/` into `sources/`, hashed, heading-split and citable |
| `/ato-glossary` | Resolve the acronyms ingest queued, one at a time |

**Assess**

| Skill | Purpose |
| --- | --- |
| `/ato-extract-claims` | Turn what a document asserts into discrete sourced claims |
| `/ato-map-controls` | Map claims onto framework controls, from the ISM OSCAL catalogue |
| `/ato-reconcile-evidence` | Judge each claim against the evidence that bears on it |
| `/ato-risk` | Draft a risk with the structure the register needs, rated from the matrix |

**Ask, check, finish**

| Skill | Purpose |
| --- | --- |
| `/ato-rfi` | Raise, close, list and export requests for information |
| `/ato-challenge` | Adversarial review of the whole assessment, cheapest run early |
| `/ato-export` | Regenerate the risk register and the report skeleton |

**Reference and state**

| Skill | Purpose |
| --- | --- |
| `/ato-status` | Where the assessment stands, derived from the files, one screen |
| `/ato-phase` | What the current phase requires, and moving the marker |
| `/ato-process` | How an assessment is conducted, phase by phase |
| `/ato-schemas` | The file contract, and what each `ATO-Exxx` denial means |
| `/ato-help` | This page |

The skills hand off in this order: `/ato-init` → `/ato-interview` → `/ato-ingest` → `/ato-extract-claims` → `/ato-map-controls` → `/ato-reconcile-evidence` → `/ato-risk` → `/ato-export`, with `/ato-glossary`, `/ato-rfi` and `/ato-challenge` running throughout. `/ato-process` sets that against the seven phases and says what each one establishes.

## How it works

- **Contract over capability.** The YAML frontmatter schemas for `sources/ claims/ evidence/ controls/ risks/ rfi/` are the whole integration surface. Anything that writes a conformant file is integrated. `/ato-schemas` has the fields.
- **Traceability is mechanical.** A claim, control or risk that cites no source is denied by a hook, not by a prompt asking the model to be careful.
- **State lives in files; status is derived.** `ato status` recomputes every number each time. Nothing about where the assessment stands is ever written down as prose, because a written one is wrong the moment anything changes.
- **Never block; degrade; record the gap.** No adapter for an input means handling it by hand, labelling it `method: ad-hoc`, and logging what was missing.

Heavy reading goes to a sub-agent so a 400-page SSP never enters the main conversation: `extractor` reads sources into claim candidates, `evidence-checker` judges one claim at a time, `challenger` reviews the whole assessment. The skills dispatch them; you never invoke one directly.

New evidence formats are integrated as separate adapter plugins rather than by changing this one. `adapters/loose-evidence/` is the reference — it records an arbitrary file as a conformant evidence entry, and proves that integrating means writing a file in the contract shape and nothing more.

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

## Guardrails

- **Answer from this page and nothing else.** Do not run `ato status` to check first, do not open the assessment, do not count anything.
- **Never say where the assessment stands.** Not the phase, not what is outstanding, not how far along it is. If that was the real question, it is `/ato-status`.
- **Do not start an assessment because someone asked what the plugin does.** Say `/ato-init` is how, and let them run it.
- **Hand off rather than paraphrase.** A question about one step is answered by that step's skill, which is current; a summary of it here is not.
