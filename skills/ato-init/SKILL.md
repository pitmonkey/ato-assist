---
name: ato-init
description: >
  Use when starting a new ATO security risk assessment and the working directory has no
  assessment.yaml yet. Scaffolds the assessment repository, captures the three
  classification fields, copies the org configuration, and makes the first commit.
  Triggers: "start an assessment", "new ATO assessment", "set up the assessment repo",
  "/ato-init", an empty directory the assessor wants to assess a system in. For an
  assessment that already exists use ato-status instead; to interview the assessor about
  the system, that is ato-interview and it comes next.
allowed-tools: [Bash, Read, Write, AskUserQuestion]
---

# ato-init

Turns an empty directory into an assessment workspace. This runs once per assessment, before anything else.

## Procedure

### 1. Refuse to scaffold over an existing assessment

If `assessment.yaml` exists in the working directory, stop. Say so, and point at `/ato-status`. Never overwrite one.

### 2. Establish the three classifications

These are three different things and conflating them is the most common way an assessment repository ends up mismarked. Ask for all three together, in one question, with the scale in front of the assessor:

| Field | Question |
|---|---|
| `classification.data` | What is the highest classification of data the system *processes*? |
| `classification.environment` | What is the classification of the *hosting environment*? |
| `classification.marking` | What marking will the assessment artefacts themselves carry? |

The scale, lowest to highest: `UNOFFICIAL`, `OFFICIAL`, `OFFICIAL:Sensitive`, `PROTECTED`, `SECRET`, `TOP SECRET`.

The marking must sit at or above both of the others — the assessment describes the system, so it inherits the higher classification. `ato init` refuses otherwise; do not try to talk the assessor past that refusal, help them pick the right marking.

**Do not proceed to any other step until all three are answered.** An assessment whose classification is unknown cannot be safely filed, and the contract hook blocks every write until it is set.

### 3. Gather the rest

Ask in one round, and accept short answers:

- System name, and a short name (lowercase, no spaces) used in output filenames.
- System owner, and who is assessing.
- Framework and profile. Default `ism` with the profile matching `classification.data` — offer that default rather than making the assessor recite it.
- Where the original documents may live: `gitignore` (default — originals stay on disk, out of git), `commit` (originals in the repository), or `reference` (originals live elsewhere, only the hash manifest is kept). If the assessor has no view, take the default and note it in `decisions.md`.

### 4. Scaffold

```
ato init . --name "<name>" --short-name <short> --owner "<owner>" --assessor "<assessor>" \
  --data "<data>" --environment "<environment>" --marking "<marking>" \
  --framework ism --profile <profile> --retain <gitignore|commit|reference>
```

This creates the layout, copies `process.yaml`, `risk-matrix.yaml` and `register-columns.yaml`, writes the workspace `CLAUDE.md` with the marking, seeds the glossary and the working files, and makes the first commit.

### 5. Record the setup decisions

Append one line to `decisions.md` for each judgement made above that was not obvious — particularly the marking, the framework, and the inbox retention choice. Date, phase, decision, why, who.

### 6. Hand over

Tell the assessor, in this order:

1. Where the assessment is and how it is marked.
2. That `process.yaml` and `risk-matrix.yaml` ship as **placeholders** and must be validated with their assessment team before the register goes anywhere near a governance board.
3. What happens next: `/ato-interview` before any document is ingested, then drop documents in `inbox/` and run `/ato-ingest`.

## Guardrails

- Never invent a classification. If the assessor does not know, stop and let them find out; there is no safe default.
- Never scaffold outside the directory the assessor is standing in without saying so.
- Do not start reading documents in this skill, even if `inbox/` already has files. Ingest is its own step and it comes after the interview.
