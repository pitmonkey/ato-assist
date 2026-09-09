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

Statuses come from the framework's own vocabulary in `frameworks/<framework>.yaml`, not from this skill. For the ISM they are `not-assessed`, `ineffective`, `alternate-control`, `effective` and `not-applicable` — what an IRAP assessment reports is control effectiveness. `ato validate` names the accepted values when a status is outside them, and a status from the old vocabulary is `ATO-E105` with its replacement.

Only the statuses the vocabulary lists as `uncited` may cite nothing — for the ISM, `not-assessed` alone. Everything else must cite at least one claim or piece of evidence, and the statuses listed as `needs_claim` must cite a **claim** specifically: scoping a control out, or accepting a compensating control in its place, is a judgement someone made and that judgement needs a source.

### 4. Leave the status alone

Mapping is not assessing. A control you have just mapped stays `not-assessed` until the assessor decides, with evidence, what it is. Do not set `effective` because a claim says the thing is done — a claim is what the system owner asserts, not proof.

The one exception: propose `not-applicable` where the profile clearly does not reach the system (a control about gateways on a system with no gateway), and put the proposal to the assessor rather than setting it.

### 5. Report coverage honestly

`ato status` counts assessed controls against the whole profile, not against the files you have written. A low percentage early is correct and useful; do not make it look better by creating `not-assessed` stubs for everything.

### 6. Commit

```
ato commit --kind map --summary "ISM PROTECTED: 118 controls mapped, 31 uncovered"
```

## Guardrails

- One claim can bear on many controls, and one control on many claims. Do not force a one-to-one mapping.
- **Never renumber a claim.** IDs are immutable: the filename carries the ID, and every control, risk and RFI that cites it resolves by that number. Renumbering after a bulk edit silently repoints citations at whatever claim now holds the old ID — the reference stays well-formed, the claim still exists, and `ato validate` passes cleanly while a control cites something unrelated to it. If a claim must go, retire it (`state: retired`) and leave the number spent.
- **Watch for a control becoming an overflow bin.** A control that accumulates a dozen or more claims is usually not well covered; it is where claims went when nobody could find a better home. Re-read its citations and move what does not bear on it.
- After any bulk edit, generation or deduplication, **re-read the citations**. `grep -rn "CLM-00NN" .` shows everything that points at a claim; check each one still means what its body text says it means. No script can tell whether a cited claim is relevant to the control citing it, and bulk operations are exactly when that goes wrong.
- If no claim bears on a control, leave it uncovered and say so. An invented mapping hides a gap, which is the worst possible outcome of this step.
- If a term in a control is undefined in this assessment, queue it and mark the control `needs-clarification` in its body — do not guess at what the ISM means by it in this context.
- Essential Eight maturity is scored separately from ISM control status. Do not blend them.
