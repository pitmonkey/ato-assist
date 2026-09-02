---
name: ato-risk
description: >
  Use when an ATO assessment needs a risk written up, rated or revised — a control gap
  that needs expressing as risk, an assessor wanting to record something they have found,
  or a risk needing its treatment or acceptance recorded. Triggers: "/ato-risk", "raise a
  risk", "write this up as a risk", "rate this", "what's the residual risk", "the
  customer wants to accept this". For the register export use ato-export.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion]
---

# ato-risk

Writes a risk with the structure the register needs, rated from the assessment's own matrix.

## Procedure

### 1. Get the four parts separately

A risk is not a sentence, it is four things, and collapsing them is how a register ends up full of entries nobody can act on:

| Part | The question |
|---|---|
| `threat` | Who or what would act? |
| `vulnerability` | What weakness lets them? |
| `consequence` | What happens to the business if they do? |
| `statement` | The three joined, as one sentence a governance board would read |

"MFA is not enabled" is not a risk — it is a vulnerability with no threat and no consequence. Ask for the missing parts rather than writing it up as it stands.

### 2. Rate it with the assessor, from the matrix

```
ato risk scales .
```

Use the scales `risk-matrix.yaml` defines, and use the assessor's words for which one applies. **Never rate a risk yourself.** Likelihood and consequence are the two most consequential judgements in an assessment and they are not yours to make.

The severity is derived from the matrix and never written into the file. If you find yourself wanting to type a rating, the matrix is wrong or the scales are — fix the matrix.

### 3. Cite what it rests on

`refs` must name at least one claim, control, source or piece of evidence. A risk with no traceability cannot survive a governance board asking "how do you know?" — and the contract hook will refuse it.

Usually the chain runs: control `not-satisfied` → the evidence that shows it → the risk. Cite the whole chain, not just the control.

### 4. Write it

```
ato next-id risks
```

```yaml
---
id: RSK-0001
title: Unmonitored privileged access to the management plane
statement: "A malicious insider could use privileged access undetected, because..."
threat: "..."
vulnerability: "..."
consequence: "..."
likelihood: possible
impact: major
refs: [ISM-0421, EVD-0007, CLM-0042]
state: draft
updated: <today>
---
```

`state: draft` until the assessor has agreed it. `owner` is required from `open` onwards; `disposition` is required once `accepted` — that is the acceptance rationale, and an accepted risk without one is the thing a board will ask about first.

### 5. Commit

```
ato commit --kind risk --summary "RSK-0001 raised from ISM-0421"
```

## Guardrails

- Never rate a risk on the assessor's behalf, and never nudge a rating because it feels high or low.
- Never write a risk without a consequence to the business. "The control is not met" is a control status, not a risk.
- Never accept a risk in the file because someone said it was fine in conversation. Acceptance is a decision with an owner and a rationale; record both, and log it in `decisions.md`.
- One risk per file. A risk covering four unrelated gaps cannot be treated or accepted as a unit.
