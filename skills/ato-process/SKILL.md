---
name: ato-process
description: >
  Use when someone asks how an ATO security risk assessment is conducted as a whole — explaining the method to a customer, a system owner or a new assessor, or laying out the shape of the work before starting it. Triggers: "/ato-process", "how does an ATO assessment work", "explain the assessment process", "what is your methodology", "walk me through the process", "what happens after claims extraction", "what order do these run in", "brief the customer on how this works". This describes the method in general and never reads the assessment: for what the current phase requires and to move the marker use ato-phase, and for where this assessment stands, ato-status.
---

# How an ATO assessment is conducted

The seven phases of the work, what each one establishes, and which skill does it.

## Who this is for

An assessor explaining the method to a customer, a system owner, or someone new to the team — and a model that needs the shape of the work before it starts offering steps. It is a description, not a controller. Nothing here starts, advances or decides anything.

## The assessment in one paragraph

A desktop review of third-party artefacts turns documents into judgements that can be traced back to the page they came from. The vendor asserts things; the assessment records each assertion as a claim citing where it was asserted, maps those claims onto the controls a framework requires, judges each claim against the evidence that bears on it, turns what is not satisfied into rated risks, and exports a register and a report. Every step is the assessor's judgement; the workbench's job is to make sure nothing gets recorded without a source and that no number is ever written down where it could go stale.

## Phases

These seven are the shipped default, from `config/process.yaml`. That file is copied into the assessment at init and the copy at the assessment root is what runs — so if a team has replaced it, theirs is authoritative and `ato phase <id>` will name theirs, not these. The _Skills_ column stays true either way, because it maps work to skills rather than to a particular team's phase ids.

| Phase | What happens | Skills |
| --- | --- | --- |
| `intake` | The assessor is interviewed about the system before any document colours the picture; then what lands in `inbox/` becomes hashed, heading-split, citable sources | `/ato-init`, `/ato-interview`, `/ato-ingest`, `/ato-glossary` |
| `claims-extraction` | Each source is read for what it asserts, and every assertion becomes a discrete claim citing where it was asserted — including the absences, which are findings too | `/ato-extract-claims`, `/ato-glossary` |
| `control-mapping` | Claims are mapped onto the controls the framework requires, and each control records what its status rests on | `/ato-map-controls` |
| `evidence-reconciliation` | Each claim is judged against the evidence bearing on it, "unevidenced" is kept apart from "gap", and what is missing becomes a request for information | `/ato-reconcile-evidence`, `/ato-rfi`, the `loose-evidence` adapter |
| `threat-mapping` | The threat picture is written down, and questions outstanding with the vendor are chased before they age | the assessor writes `notes/threats.md`, seeded at init; `/ato-rfi` |
| `risk-extraction` | An unsatisfied control becomes a risk with the four parts the register needs, rated against the assessment's own matrix | `/ato-risk` |
| `report` | The register and the report skeleton are regenerated from the files, and the assessor writes the prose that only they can write | `/ato-export`, `/ato-challenge` |

The work, in the order the skills hand off to one another: `/ato-init` → `/ato-interview` → `/ato-ingest` → `/ato-extract-claims` → `/ato-map-controls` → `/ato-reconcile-evidence` → `/ato-risk` → `/ato-export`. That is the order to offer work in, and it runs alongside the phases above rather than against them. If you change it, the same line in `/ato-help` changes with it.

The criteria that gate each phase are not repeated here. They live in `process.yaml` at the assessment root, they are the team's to set, and `/ato-phase` prints them live against the current state. A copy on this page would be a second account, going stale from the moment a team edits theirs.

Three skills belong to no phase and run throughout: `/ato-glossary` empties the queue of undefined terms; `/ato-rfi` tracks what the assessment is waiting on and who from; `/ato-challenge` puts the whole thing past an adversarial reviewer, and is cheapest early. `/ato-status`, `/ato-phase` and `/ato-schemas` are reference and state, not work.

## What the workbench guarantees

- **Nothing gets recorded without a source.** A claim, control or risk that cites nothing is denied by a hook, not by a prompt telling the model to be careful.
- **Status is derived, never written.** `ato status` recomputes every number from the files each time it runs, so there is no prose account of where things stand that can be wrong.
- **Anything that writes a conformant file is integrated.** The frontmatter schemas are the whole integration surface; an adapter is a skill that writes one, and `adapters/loose-evidence/` is the reference.
- **A missing tool degrades, it does not block.** No adapter for an input means handling it by hand, labelling it `method: ad-hoc`, and logging the gap — never stopping.

## Guardrails

- **Describing the process is not permission to run it.** Printing this page starts no phase, extracts nothing and writes nothing.
- **Never say which phase this assessment is in.** That is `/ato-status`, which derives it from the files. Do not infer it from what has been discussed.
- **Never move the phase marker** — not because criteria pass, and not because the order above says this step is next. Only the assessor moves it, through `/ato-phase`.
- **This is the order to offer work in, not to do it.** Every judgement the work produces — whether a claim is met, whether a control is satisfied, what a risk rates — is the assessor's.
- **Do not write this into the assessment.** No `notes/process.md`, no summary in `decisions.md`, and never a status paragraph anywhere.
- **The team's `process.yaml` outranks this page.** Where they differ, theirs is right and this is the shipped default.
- **"Are we done with this phase?" is not answered from here.** That is exit criteria, and it is `/ato-phase`.
