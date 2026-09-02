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

### 1. Find the candidates in the assessment

Risks are not something the assessor arrives holding. By the time an assessment reaches this phase it contains 100+ claims, a mapped control set, recorded contradictions and one or more challenge reports, and **the candidates are already in there**. Read for them before asking the assessor anything, and bring a list.

Three places they come from, and the second is the one most assessments miss:

**A control that cannot be assessed without evidence.** The classic chain: control `not-satisfied` → the evidence showing it → the risk. This is the case the register is built around, and it needs the customer to have answered.

**A control the document itself admits is not implemented.** A narrative saying "a control response is planned", or "there seems to be a gap", or claiming a status while its own text describes the opposite, is *the system owner asserting in writing that the control is not in place*. That is a documented admission, not an assessor's unevidenced judgement, and **it is assessable today on the document alone.** No RFI has to come back first. In an assessment where every control is `not-assessed` and no evidence exists, this is the entire raisable set — and it is the difference between weeks of dead time waiting on the customer and none.

**A finding that is risk-shaped without being a control gap.** A plan that sets a test in its own preamble which it cannot pass; a boundary the document never states; an attachment inventory listing eleven of fourteen artefacts as not supplied. These are risks about the *assessment's source material* rather than about the system, and they belong in the register because they bear on whether an authorisation decision can be made at all. `refs` takes a `SRC-` reference like any other — a risk about the document cites the document.

Work the batch. An assessment entering this phase has a handful of candidates at once, not one; draft them together and put them to the assessor as a set, because the relative severity of five risks is easier to judge than the absolute severity of one.

### 2. Get the four parts separately

A risk is not a sentence, it is four things, and collapsing them is how a register ends up full of entries nobody can act on:

| Part | The question |
|---|---|
| `threat` | Who or what would act? |
| `vulnerability` | What weakness lets them? |
| `consequence` | What happens to the business if they do? |
| `statement` | The three joined, as one sentence a governance board would read |

"MFA is not enabled" is not a risk — it is a vulnerability with no threat and no consequence. Ask for the missing parts rather than writing it up as it stands.

### 3. Rate it with the assessor, from the matrix

```
ato risk scales .
```

Use the scales `risk-matrix.yaml` defines, and use the assessor's words for which one applies. **Never rate a risk yourself.** Likelihood and consequence are the two most consequential judgements in an assessment and they are not yours to make.

**Three fields are the assessor's and only the assessor's: `owner`, `likelihood`, `impact`.** That is the line where your authority stops. Everything a document can establish — the threat, the vulnerability, the consequence, the statement, every reference — you fill in. Everything requiring a judgement about this organisation's tolerance for this outcome, you leave empty and say you have left it. An agent that fills those three has not saved the assessor work, it has made a decision in their name and hidden it in a file.

**A draft may be filed without them.** `likelihood` and `impact` are required only from `state: open` onwards, so the honest thing to do is write the risk complete in every respect you can establish — threat, vulnerability, consequence, statement, references — and leave those two empty for the assessor. `ato risk list` shows such a risk as `has not been rated yet`, which is different from a rating the matrix does not recognise. Do that rather than guessing a rating you intend to correct, and rather than not writing the risk until someone is available.

The severity is derived from the matrix and never written into the file. If you find yourself wanting to type a rating, the matrix is wrong or the scales are — fix the matrix.

### 4. Cite what it rests on

`refs` must name at least one claim, control, source or piece of evidence. A risk with no traceability cannot survive a governance board asking "how do you know?" — and the contract hook will refuse it.

Where the chain runs control `not-satisfied` → the evidence that shows it → the risk, cite the whole chain rather than just the control.

Where it does not — a documented admission, or a finding about the document itself — cite what actually establishes it: the claim carrying the admission, the control it bears on, and the source section. A risk resting on the document's own words is as traceable as one resting on evidence, and often more so.

### 5. Write it

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

### 6. Commit

```
ato commit --kind risk --summary "RSK-0001 raised from ISM-0421"
```

## Guardrails

- Never rate a risk on the assessor's behalf, and never nudge a rating because it feels high or low.
- Never write a risk without a consequence to the business. "The control is not met" is a control status, not a risk.
- Never accept a risk in the file because someone said it was fine in conversation. Acceptance is a decision with an owner and a rationale; record both, and log it in `decisions.md`.
- One risk per file. A risk covering four unrelated gaps cannot be treated or accepted as a unit.
- Never wait for evidence to raise a risk the document already admits. "The control response is planned" is the owner saying it is not in place; an RFI will not make that truer.
- Never rate a draft to make it look finished. An unrated draft is a question waiting for the assessor; a guessed rating is an answer nobody gave.
- Never require a risk to cite a claim or a control. A risk about the document cites the document, and a rule demanding otherwise would be satisfied by citing a claim that half-covers it — which makes the traceability worse, not better.
