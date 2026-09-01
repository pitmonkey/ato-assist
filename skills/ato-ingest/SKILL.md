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

It hashes each file, skips anything already ingested unchanged, converts documents to markdown, splits them on headings into `sources/SRC-NNNN-<slug>/`, queues undefined acronyms, and logs any gap where a converter was missing.

Read what it reports. It will tell you what was ingested, what was a revision of something already there, what it could not read, and how many terms it queued.

### 2. Set the classification of each new source

Ingest writes `classification: UNOFFICIAL` because it cannot know. Ask the assessor once, for all new sources together, and correct each `index.md`. A source marked below its true classification is a marking failure, not a paperwork one.

### 3. Ask what a revision changed, not whether it changed

For a superseding revision, the report gives you the section counts. Open the changed sections and say plainly what moved. Do not re-read the whole document — the earlier version's claims are still valid unless the text under them changed.

Where a changed section underpins existing claims, list those claims for the assessor and ask whether each still holds. Do not silently update a claim.

### 4. Ask whether anything closes an open RFI

If `rfi/` has anything in `open` or `blocked`, list them with what arrived, and ask which — if any — this satisfies. An RFI is closed by a source landing, so record the closing source in `answer_source`. Never close one on your own judgement.

### 5. Report the gaps, do not solve them

Anything ingest could not read is a source with a stub and a question. Put the questions to the assessor as a batch. Do not attempt to transcribe a diagram or guess at a scanned document's contents.

### 6. Commit

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
