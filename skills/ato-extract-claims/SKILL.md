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

For each section of the source, dispatch the `extractor` sub-agent against `sources/SRC-NNNN-<slug>/`. It reads in a fresh context and returns candidates, absences and undefined terms — never the document.

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
- Never write a claim from the interview notes. `notes/system-context.md` has no source and is not a document; it is context, not assertion.
- Never assess a claim here. Whether it is met is `/ato-reconcile-evidence` and `/ato-map-controls`.
