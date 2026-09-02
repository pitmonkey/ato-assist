---
name: ato-export
description: >
  Use when an ATO assessment's risk register or report needs generating or regenerating —
  for a governance board, a customer, or a review. Triggers: "/ato-export", "export the
  register", "generate the report", "produce the risk register", "what goes to the
  board". To raise or rate the risks that go in it use ato-risk.
allowed-tools: [Bash, Read]
---

# ato-export

Regenerates the risk register and the report skeleton from the files.

## Procedure

### 1. Check the assessment is fit to export

```
ato validate .
ato status .
```

Do not export over the top of unresolved problems. In particular:

- **A placeholder configuration still flagged.** `risk-matrix.yaml` and `register-columns.yaml` ship as authored placeholders. A register produced against a matrix the organisation has not agreed is not a register a board can act on. Say this plainly before exporting, every time, until the flag is gone.
- **Risks rated off the scales.** These export as `unrated` and will be the first thing anyone notices.
- **Accepted risks with no disposition.** A board will ask why it was accepted; the file should already say.
- **Draft risks.** Decide with the assessor whether they belong in this export.

### 1b. Check the facts the report prints as though they were established

**Every field `ato init` asked for was answered before the assessment knew anything about the system**, and several are printed on the first page of the report: the system name, the owner, the assessor, the scope. Nothing revisits them. The classification gets revisited because a check exists for it; the owner does not, and a report has gone to draft stating that the assessor owned the system being assessed.

Before exporting, read the header block of `assessment.yaml` against the documents. For each field, ask where in `sources/` it is established, and correct it — with a line in `decisions.md` — where the answer is "nowhere" or "it disagrees".

`ato validate` warns (`ATO-E311`) where the owner and the assessor are the same person, which is the case that has actually happened, but it cannot check the rest. That part is reading.

### 2. Export

```
ato export            # register (csv and xlsx) and report skeleton
ato export register
ato export report
```

Everything lands in `outputs/` with the assessment marking on the first line of every file.

**Unrated risks come first, then the rated ones worst-first.** An unrated risk is outstanding work rather than a low severity; sorting it to the bottom would make the register imply it is the least severe, which is the one thing it cannot support. If the top of a register is a block of unrated rows, that is the register reporting accurately that the assessment is not finished.

### 3. Write the prose, do not invent the numbers

The report skeleton arrives with the counts, the risk list, the source table and the open RFIs already filled in. The sections that remain are judgement: the executive summary, the method, the findings, the recommendation.

Draft them **with** the assessor, from what is in the files. Every statement in the report must be traceable to a claim, a control or a risk. If you cannot point to the file behind a sentence, that sentence does not go in.

### 4. Say what was not done

The method section is the one most often quietly softened. State what was not assessed and why — not read, not tested, not provided. An assessment that hides its own gaps is not usable, and the gaps are already visible in `tooling-gaps.md`, the open RFIs and the unevidenced claims.

### 5. Commit

```
ato commit --kind export --summary "risk register and report for the September board"
```

## Guardrails

- **Never hand-edit anything in `outputs/`.** It is regenerated; an edit there is lost on the next export and disagrees with the files in the meantime. Fix the source file and export again.
- Never adjust a rating to make a register read better.
- Never write a number into the report that is not in `ato status`.
- **Never state a count without its denominator.** "not-assessed: 47" with no universe anywhere in the document lets a reader take 47 for the whole framework. The skeleton now prints coverage against the applicable profile; if you add a count of your own, add what it is out of.
- The marking on every output is a real classification decision. If the assessor wants it changed, that is a change to `assessment.yaml`, not to the file header.
