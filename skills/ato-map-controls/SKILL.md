---
name: ato-map-controls
description: >
  Use when an ATO assessment has extracted claims that need mapping onto framework
  controls — ISM, or Essential Eight maturity levels. Triggers: "/ato-map-controls",
  "map to the ISM", "which controls does this cover", "control mapping", "what's the
  coverage against PROTECTED", a phase whose exit criteria mention controls. To extract
  the claims first use ato-extract-claims; to judge whether the evidence supports them,
  ato-reconcile-evidence.
allowed-tools: [Bash, Read, Write, Glob, Grep, AskUserQuestion]
---

# ato-map-controls

Maps claims onto the controls a framework requires, and records what each control's status rests on.

## Procedure

### 1. Read the catalogue, never recite it

```
ato controls --profile PROTECTED       # what applies at this classification
ato controls --search "multi-factor"   # candidates for a claim
ato controls ISM-0421                  # one control in full
```

**Never write control text from memory into a file.** The ISM is revised; a control recited from memory is wrong the moment it changes and nobody notices. Everything you write about what a control requires comes from `ato controls`.

### 2. Work claim-first, then sweep control-first

Start from the claims: for each, search the catalogue and propose the controls it bears on. This finds the coverage that exists.

Then sweep the other way: walk the profile and find controls **no claim touches**. This is the part that matters — uncovered controls are where the gaps are, and a claim-first pass alone will never surface them.

### 3. Write the control file

`controls/ism/ISM-0421.md`:

```yaml
---
id: ISM-0421
framework: ism
title: <from `ato controls ISM-0421`>
status: not-assessed
claims: [CLM-0042]
evidence: []
confidence: medium
method: document-review
updated: <today>
---
What the control requires, and how the cited claims bear on it.
```

Statuses: `not-assessed`, `satisfied`, `partially-satisfied`, `not-satisfied`, `not-applicable`, `inherited`.

Anything other than `not-assessed` must cite at least one claim or piece of evidence — the contract hook enforces it. `not-applicable` and `inherited` must cite a **claim**, because scoping a control out or inheriting it is a judgement someone made and that judgement needs a source.

### 4. Leave the status alone

Mapping is not assessing. A control you have just mapped stays `not-assessed` until the assessor decides, with evidence, what it is. Do not set `satisfied` because a claim says the thing is done — a claim is what the system owner asserts, not proof.

The one exception: propose `not-applicable` where the profile clearly does not reach the system (a control about gateways on a system with no gateway), and put the proposal to the assessor rather than setting it.

### 5. Report coverage honestly

`ato status` counts assessed controls against the whole profile, not against the files you have written. A low percentage early is correct and useful; do not make it look better by creating `not-assessed` stubs for everything.

### 6. Commit

```
ato commit --kind map --summary "ISM PROTECTED: 118 controls mapped, 31 uncovered"
```

## Guardrails

- One claim can bear on many controls, and one control on many claims. Do not force a one-to-one mapping.
- If no claim bears on a control, leave it uncovered and say so. An invented mapping hides a gap, which is the worst possible outcome of this step.
- If a term in a control is undefined in this assessment, queue it and mark the control `needs-clarification` in its body — do not guess at what the ISM means by it in this context.
- Essential Eight maturity is scored separately from ISM control status. Do not blend them.
