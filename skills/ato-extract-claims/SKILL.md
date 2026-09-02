---
name: ato-extract-claims
description: >
  Use when an ATO assessment has ingested sources that no claim cites yet, and the SSP's
  assertions need turning into discrete, sourced claims. Triggers: "/ato-extract-claims",
  "extract the claims", "pull the assertions out of the SSP", "turn the SSP into claims",
  a status screen showing sources never cited by a claim. To ingest a document first use
  ato-ingest; to map the resulting claims onto framework controls, ato-map-controls.
allowed-tools: [Bash, Read, Write, Glob, Grep, Task, AskUserQuestion]
---

# ato-extract-claims

Turns what a document asserts into discrete claims, each citing where it was asserted.

## Procedure

### 1. Find what has not been extracted

```
ato status .
```

The `sources never cited by a claim` count is the backlog. Work one source at a time; a source at a time is reviewable, a whole assessment at once is not.

### 2. Dispatch the extractor, do not read the document yourself

Dispatch the `extractor` sub-agent against **batches of sections**, not against each section and not against the whole source.

Aim for six to twelve dispatches for a large document, each covering a coherent group of sections — a chapter, a control family, a topic. On a 400-section SSP that is roughly thirty sections per dispatch. One agent per section would be hundreds of dispatches for one document; one agent for the whole source cannot hold it. Both are wrong, in opposite directions.

Group by what the document is about, not by file count. Front matter, then AC/AT, AU/CA/CM, and so on for a control-structured document; by chapter for a narrative one. A batch that spans unrelated material produces vaguer candidates.

Tell each extractor, explicitly, in the dispatch:

- The source ID and the exact section files it covers.
- **A cap of about three candidates per control or section.** Left uncapped on a control-structured SSP, extraction emits a thousand near-duplicates.
- **Framework control text is never a claim.** An SSP built from a catalogue template quotes the catalogue's own requirement wording in every control block. That text says what the framework requires, not what this system does, and a claim extracted from it is a claim about the catalogue. On an 800-53 or ISM-templated document this is the single most important instruction in the dispatch — without it, most of what comes back is restated framework text wearing a claim's frontmatter.

**Do not read a large document into this conversation.** Once an SSP is in the main context, every later step in the session is worse and the context is gone for the work that actually needs it.

### 3. Write each candidate as a claim

```
ato next-id claims
```

Then write `claims/CLM-NNNN-<slug>.md`:

```yaml
---
id: CLM-0042
title: Privileged access requires MFA
statement: "All privileged access requires phishing-resistant MFA."
source:
  - ref: SRC-0007#privileged-access
    locator: "p.34"
    quote: "All privileged access requires phishing-resistant MFA."
state: draft
confidence: medium
method: document-review
updated: <today>
---
```

`state: draft` until the assessor has looked at it. `confidence` is about how clearly the document asserts it, not about whether it is true — a crisp assertion in a badly-out-of-date document is still `high` confidence *as an extraction*.

`method: document-review` normally. If the source was handled ad hoc — the index will say so — use `ad-hoc`, and confidence cannot then exceed `medium`.

### 4. Record the absences

The extractor returns what the document conspicuously does not say. These are not claims. Put them in `notes/absences.md` with their section reference. Several will become RFIs, and some will become risks.

### 5. Queue the terms, do not chase them

Undefined terms go to `glossary/unresolved.md`. Any claim that turns on one gets `state: needs-clarification`. Do not stop, and do not guess what the acronym means.

### 6. Put the batch to the assessor

Show the claims as a list — ID, statement, source — and ask which are accurate extractions. Move those to `asserted`. This is a review of *whether the document says this*, not of whether it is true; do not let the conversation drift into assessment yet.

### 7. Commit

```
ato commit --kind extract --summary "SRC-0007: 31 claims"
```

## Guardrails

- A claim with no source is refused by the contract hook. That is the mechanism working — find the reference, never reword the claim to get past it.
- Never merge two assertions into one claim because they are adjacent. Different evidence, different claim.
- Never extract a claim from framework control text, however specific it sounds. "The organisation implements multi-factor authentication" in a requirement box is the catalogue talking.
- If a source is marked `anchors_unavailable`, it has no sections to cite. Do not extract against it — say so, and offer to prepare the document and re-ingest.
- Never write a claim from the interview notes. `notes/system-context.md` has no source and is not a document; it is context, not assertion.
- Never assess a claim here. Whether it is met is `/ato-reconcile-evidence` and `/ato-map-controls`.
