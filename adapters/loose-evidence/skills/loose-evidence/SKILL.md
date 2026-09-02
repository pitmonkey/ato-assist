---
name: loose-evidence
description: >
  Use when the assessor has a file that is evidence for an ATO assessment but nothing
  understands its format — a screenshot, a config dump, a vendor letter, an export from
  a tool with no adapter. Triggers: "/loose-evidence", "record this as evidence", "add
  this screenshot", "here's the export, it bears on CLM-0042", "no adapter for this".
allowed-tools: [Bash, Read, Edit, AskUserQuestion]
---

# loose-evidence

Records an arbitrary artefact as a conformant evidence entry. This is the reference adapter: it proves that integrating with the workbench means writing a file in the contract shape, and nothing more.

## Procedure

### 1. Get the two things only a human can supply

- **What it is**, in one line. Not the filename — what it demonstrates.
- **Which claims it bears on.** At least one claim ID. If the assessor does not know, list candidate claims from `claims/` and ask; do not guess.

### 2. Record it

```
ato evidence add --file <path> --describe "<one line>" --bears-on CLM-0042 \
  --direction supports --collected-by "<who provided it>"
```

This copies the artefact into `evidence/artifacts/`, hashes it, and writes a `draft` entry labelled `method: ad-hoc`.

`ad-hoc` is correct and is not an apology. Nothing has parsed the file; a human looked at it. That label caps the confidence of anything resting on it, which is exactly right.

### 3. Say what it actually shows

The entry's body has an `## Assessor note` heading waiting. Fill it in with the assessor:

- What the artefact demonstrates.
- **For what scope** — which environment, which tenant, which subset.
- **As at when** — evidence is a statement about the moment it was collected.

An evidence entry that says "conditional access export" and nothing else is a filename with extra steps.

### 4. Log the gap, if it recurs

If this kind of artefact keeps arriving, add a line to `tooling-gaps.md`. The entries that recur are the adapters worth building — that file is the backlog.

### 5. Move it out of draft

Once the assessor has confirmed what it shows, set `state: accepted`.

## Writing your own adapter

Everything above is mechanics. An adapter for a specific evidence source does the same thing with the reading automated:

1. Parse the source into whatever it says.
2. Write `evidence/EVD-NNNN-<slug>.md` with `bears_on`, `direction`, `artifact`, `method: adapter:<your-name>`, `collected`, `collected_by`, `integrity` and `state`.
3. Say what it shows in the body, with scope and date.

No API, no registration, no coupling to this plugin. Write a conformant file and you are integrated — the contract hook will tell you immediately if you are not.
