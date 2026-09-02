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

### 3. Verify each finding against the source before acting on it

**A finding handed to you needs checking exactly as much as one you found yourself.** This is the step that gets skipped, and skipping it is how a review makes an assessment worse.

The remediation frame is what makes it dangerous. You have just been shown you were wrong, the reviewer has authority it earned by being right about other things, and the cheapest path is to apply what it says. In a real assessment both over-corrections came through that channel — a contradiction correctly identified as a non-contradiction, but stated too strongly, and a section number simply misremembered and then copied into `decisions.md` where it sat justifying a classification.

So for each finding: open the section it cites, and read it. Confirm the quote, confirm the section number, confirm the scope of the claim being made. A finding that is right in a narrower form is the common case, and the narrow form is usually the better finding.

### 4. Put the findings to the assessor, unfiltered

Show every finding, including the ones your verification narrowed. Do not pre-filter, do not soften, and do not argue with the reviewer on the assessment's behalf. The assessor decides which are real; your job was to check what each one actually says.

For each, offer the three possible answers plainly: fix it, disagree with it, or accept it and record why.

### 5. Record the disagreements

A finding the assessor rejects gets a line in `decisions.md` saying what was rejected and why. That line is what protects the assessment later — "we considered this and here is our reasoning" is a defence; silence is not.

### 6. Act on the rest

Findings usually become one of: a claim's state changing, a control's status changing, a new risk, or an RFI. Do those through the skills that own them, not by hand-editing.

### 7. Commit

```
ato commit --kind note --summary "challenge: 4 high, 9 medium; 2 rejected with reasons"
```

## When to run it

At least once before the report. Also worth it at the end of control mapping, when `not-applicable` decisions are fresh and cheap to revisit.

## Guardrails

- Never dismiss a finding yourself on the grounds that it is inconvenient. You dispatched the reviewer; you do not get to overrule it because you disagree.
- **But never apply one unverified either.** Narrowing a finding after reading the source is not overruling it — it is the work. A reviewer that is right about eight things and slightly too strong about the ninth is the normal case, and the ninth is the one that will end up asserted in the assessment's own voice.
- **Never edit a quote while rewriting a claim.** A statement is yours to reword; a quote is not. Dropping three words from a quote is what turned a live contradiction into a settled question in a real assessment, while an RFI was still out asking about it. `ato validate` now checks every quote against the section it cites, but it cannot check one you changed in both places.
- Never present "no findings" without saying what was looked for. A challenger that failed to find something and an assessment that contains nothing to find look identical from here; the only way to tell them apart is whether the rest of its findings show it was reading carefully. An assessment with none is rare enough to be suspicious.
- Do not run the challenger against a half-populated assessment and treat its orphan findings as real — early on, uncited sources are normal.
