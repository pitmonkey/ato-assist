---
name: ato-ingest
description: >
  Use when documents are waiting in an ATO assessment's inbox/ and need to become
  citable sources — an SSP, a policy, an evidence export, a revised version of something
  already ingested. Triggers: "/ato-ingest", "ingest the SSP", "I've dropped the
  documents in", "process the inbox", "here's version 2.4", new files reported by the
  session brief. For extracting claims out of what has already been ingested use
  ato-extract-claims instead; to resolve the acronyms this queues, ato-glossary.
allowed-tools: [Bash, Read, Grep, Glob, AskUserQuestion, Task]
---

# ato-ingest

Turns what landed in `inbox/` into `sources/`: hashed, split by heading, and citable by ID.

## Procedure

### 1. Run the ingest

```
ato ingest .
```

It hashes each file, skips anything already ingested unchanged, converts documents to markdown, splits them into `sources/SRC-NNNN-<slug>/`, queues undefined acronyms, and reports the section count per source.

**If it refuses, it is telling you something worth hearing.** A missing converter that would destroy document structure stops the run before anything is written (exit 3). Install the converter and run again. `--force` accepts the degraded ingest, and is the right answer only when the converter genuinely cannot be installed — say so to the assessor rather than reaching for it quietly.

**Read the `!!` lines.** Ingest checks the *outcome*, not just the converter, because the dangerous failure looks like success: a document converted cleanly but with no headings produces parts nobody can cite by section, and a document whose sections are all heading-and-nothing-else is worse. Either way ingest says so, marks the source `method: ad-hoc`, and sets `anchors_unavailable`. That source cannot support claim extraction as it stands — tell the assessor, and offer to prepare the document properly and re-ingest:

```
ato ingest . --reingest SRC-0001
```

That discards the source and reads the original again, keeping its ID so every claim citing it still resolves, and cleaning up the glossary terms the failed run queued. Never hand-delete a source directory.

It carries across what a person decided rather than what ingest worked out — the classification, and anything the assessor wrote in the index body, which comes back under `## Retained from the previous ingest`. Read that section after a reingest: prose written about the *previous* conversion may not describe the new one, and it is yours to reconcile.

**Read the `!` framework lines.** If a document names a framework the assessment is not configured for — an SSP written against NIST 800-53 being assessed against the ISM — ingest says so. That mismatch will otherwise surface at control mapping as apparent non-compliance when the real problem is that the system was documented to a different catalogue. Put it to the assessor now; it is a scoping decision, not a finding.

### 2. Set the classification of each new source

Ingest writes `classification: UNOFFICIAL` and `classification_by: ingest-default`, because it cannot know. Ask the assessor once, for all new sources together, and correct each `index.md` — **both fields**:

```yaml
classification: PROTECTED
classification_by: assessor
```

`ato validate` warns (`ATO-E309`) about any source a claim cites while the classification is still the one ingest guessed at, so leaving the second field is what tells the sweep a person has looked. A deliberate `UNOFFICIAL` is fine and stays quiet, as long as `classification_by: assessor` says someone chose it.

A source marked below its true classification is a marking failure, not a paperwork one.

### 3. Ask what a revision changed, not whether it changed

For a superseding revision, the report gives the added, changed and removed section counts. Open the changed sections and say plainly what moved. Do not re-read the whole document — the earlier version's claims are still valid unless the text under them changed.

Where a changed section underpins existing claims, list those claims for the assessor and ask whether each still holds. Do not silently update a claim.

### 4. Work the interview's open questions

`notes/system-context.md` carries a `## Open questions` checklist — what the assessor could not answer before the documents arrived. `ato status` counts the unticked ones. This is what ingest was for.

For each unticked question, say whether the documents now answer it, and where. Then let the assessor tick it. **Mentioning a topic is not answering a question** — a document with a heading called "Authorisation boundary" and nothing under it answers nothing.

Anything still unticked once every document is in becomes an RFI. That is the first round of questions to the customer, and it is already written.

### 5. Ask whether anything closes an open RFI

If `rfi/` has anything in `open` or `blocked`, list them with what arrived, and ask which — if any — this satisfies. An RFI is closed by a source landing, so record the closing source in `answer_source`. Never close one on your own judgement.

### 6. Report the gaps, do not solve them

Anything ingest could not read is a source with a stub and a question. Put the questions to the assessor as a batch. Do not attempt to transcribe a diagram or guess at a scanned document's contents.

### 7. Commit

```
ato commit --kind ingest --summary "<what arrived>"
```

## Reading the documents

**Do not load a large document into this conversation.** Dispatch the `extractor` sub-agent against the source directory and have it return structure, not prose. A 400-page SSP read into the main context makes every later step worse.

Extraction into `claims/` is a separate step — `/ato-extract-claims`. Ingest stops once the document is on disk, split, and marked.

## Guardrails

- Never edit a chunk file to "clean it up". `sources/` is the record of what the document said; a correction belongs in a claim or an assessor note, not in the source.
- Never guess at an acronym. Ingest has already queued it; leave it queued.
- Never set a classification you were not told.
- If a converter is missing, that is a logged gap and lower confidence — not a reason to stop and not a reason to ask permission.
