---
name: ato-challenge
description: >
  Use when an ATO assessment is ready for adversarial review — before a report goes out,
  before a phase moves, or when the assessor wants to know what a reviewer will find.
  Triggers: "/ato-challenge", "challenge this", "poke holes in it", "what have we
  missed", "review the assessment", "what would a reviewer say". For mechanical schema
  problems use `ato validate`; this is for the judgements a script cannot make.
allowed-tools: [Bash, Read, Glob, Grep, Task]
---

# ato-challenge

Runs the assessment past an adversarial reviewer, early enough that the findings still cost nothing to fix.

## Procedure

### 1. Clear the mechanical problems first

```
ato validate .
ato status .
```

Schema errors, dangling references and failing exit criteria are already found by these. Fix them before challenging, so the reviewer's attention goes where only judgement helps.

### 2. Dispatch the challenger

Dispatch the `challenger` sub-agent against the assessment. It hunts for claims contradicted by their evidence, controls satisfied on assertion alone, `not-applicable` and `inherited` judgements whose cited claim does not argue them, unsatisfied controls with no risk, stale evidence, and scope drift.

### 3. Put the findings to the assessor, unfiltered

Show every finding. Do not pre-filter, do not soften, and do not argue with the reviewer on the assessment's behalf. The assessor decides which are real.

For each, offer the three possible answers plainly: fix it, disagree with it, or accept it and record why.

### 4. Record the disagreements

A finding the assessor rejects gets a line in `decisions.md` saying what was rejected and why. That line is what protects the assessment later — "we considered this and here is our reasoning" is a defence; silence is not.

### 5. Act on the rest

Findings usually become one of: a claim's state changing, a control's status changing, a new risk, or an RFI. Do those through the skills that own them, not by hand-editing.

### 6. Commit

```
ato commit --kind note --summary "challenge: 4 high, 9 medium; 2 rejected with reasons"
```

## When to run it

At least once before the report. Also worth it at the end of control mapping, when `not-applicable` decisions are fresh and cheap to revisit.

## Guardrails

- Never dismiss a finding yourself. You dispatched the reviewer; you do not get to overrule it.
- Never present "no findings" without saying what was looked for. An assessment with none is rare enough to be suspicious.
- Do not run the challenger against a half-populated assessment and treat its orphan findings as real — early on, uncited sources are normal.
