---
name: ato-reconcile-evidence
description: >
  Use when an ATO assessment has claims and evidence that need judging against each other
  — does the evidence actually support what was asserted, and where is there no evidence
  at all. Triggers: "/ato-reconcile-evidence", "does the evidence support this", "check
  the claims against the evidence", "reconcile", "which claims are unevidenced", a status
  screen flagging claims with no evidence. To record new evidence use the loose-evidence
  adapter or write an evidence entry; to map controls, ato-map-controls.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, Task, AskUserQuestion]
---

# ato-reconcile-evidence

Judges each claim against the evidence that bears on it, and keeps "unevidenced" apart from "gap".

## The distinction this whole skill exists for

- **Gap** — the control is not in place. A finding about the system.
- **Asserted but unevidenced** — the system owner says it is in place and nobody has checked. A finding about the *assessment*.

They lead to different actions: a gap becomes a risk, an unevidenced claim becomes an RFI. Reporting one as the other either invents findings or hides them.

## Procedure

### 1. Find the claims that need judging

```
ato status .
```

The `claims with no evidence` count is the unevidenced pile. Claims that do have evidence still need judging — evidence bearing on a claim is not the same as evidence supporting it.

### 2. One claim at a time, through the sub-agent

Dispatch `evidence-checker` per claim, with the claim and the evidence entries whose `bears_on` names it. It returns a verdict, the scope the verdict covers, its reasoning, and what would settle it.

One claim per dispatch. Batching them produces averaged, hedged verdicts.

### 3. Record the verdict where it belongs

- `supported` → the claim moves to `corroborated`.
- `contradicted` → the claim moves to `refuted`. This is a finding; it will usually become a risk.
- `partly-supported` → the claim stays `asserted`, and the body records exactly which part is covered and which is not.
- `unevidenced` → the claim stays `asserted`. Do **not** mark it refuted, and do not mark the related control `not-satisfied`.

The evidence entry's own `direction` records what it showed. Update it if the sub-agent's reading differs from what was recorded when it was collected.

### 4. Turn what is missing into RFIs

The sub-agent's `missing` field is written to be actionable. Raise an RFI from it:

```
ato rfi new --question "<the missing field, as a request>" --asked-of "<who>" --reason CLM-0042
```

### 5. Update the controls, carefully

A control's status follows from its claims and evidence, but it is the assessor's call, not an arithmetic result. Propose the change and say what it rests on; let them decide.

A control whose claims are all unevidenced is **not** `not-satisfied`. It is still `not-assessed`, and the reason is that nobody has looked.

### 6. Commit

```
ato commit --kind evidence --summary "31 claims reconciled: 18 corroborated, 2 refuted, 11 unevidenced"
```

## Guardrails

- Never treat the absence of evidence as evidence of absence.
- Never let evidence from one environment settle a claim about another. Scope is part of the verdict.
- Never quietly discount old evidence — say how old it is and let the assessor decide.
- Never mark a claim `corroborated` on the strength of a second claim. Claims corroborate nothing; only evidence does.
