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
- **The staging path to write to**, `.ato/staging/<SRC-ID>-<batch>.yaml`, and that it must reply with the path and the counts only. A reply carrying candidates inline truncates at roughly 16 KB, and one control family exceeds that — silently, from the end of the list. The hook confines the extractor to `.ato/staging/`, so it cannot write anywhere else even by accident.
- **To collapse repeated boilerplate.** A catalogue-templated plan repeats one sentence across a whole family — twenty-six controls, one assertion. One candidate whose `refs` lists every section it appeared in, never twenty-six identical ones. Substantive narratives and contradictions are never collapsed.
- **A cap of about three candidates per control or section.** Left uncapped on a control-structured SSP, extraction emits a thousand near-duplicates.
- **Framework control text is never a claim.** An SSP built from a catalogue template quotes the catalogue's own requirement wording in every control block. That text says what the framework requires, not what this system does, and a claim extracted from it is a claim about the catalogue. On an 800-53 or ISM-templated document this is the single most important instruction in the dispatch — without it, most of what comes back is restated framework text wearing a claim's frontmatter.

**Do not read a large document into this conversation.** Once an SSP is in the main context, every later step in the session is worse and the context is gone for the work that actually needs it.

### 3. Check every result before writing anything

Each extractor replies with a staging path and counts. Before you write a single claim:

- **Read the reply for a truncation marker.** `[result truncated ...]` means the result is incomplete, not that it is the whole set. Treat it as a failed dispatch: ask the agent for the rest, or re-dispatch that batch smaller.
- **Open the staging file and check it parses**, and that its candidate count matches what the reply claimed.
- **Say plainly if a batch is incomplete.** A partial extraction still cites the source, so `every-source-claimed` will tick and the phase gate will pass on an extraction that quietly dropped half its output.

**Why this matters more than it looks.** The contract hook checks the shape of a claim, not its authorship — a well-formed claim citing a real source and a real quote passes every check whether an extractor found it or not, and `ato validate` will report `0 problems` either way. That has been demonstrated with a deliberately fabricated claim, which nothing caught.

So this count check is not bookkeeping against truncation. **It is the only check that the claims in the register correspond to something an extractor actually found.** Nothing downstream will catch a discrepancy, because nothing downstream can see one. Spot-check a few quotes against the sections they cite while you are here; that is the other half of the same defence.

Never move the phase on a run where any batch was truncated or unverified.

### 4. Write each candidate as a claim

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

A collapsed candidate keeps every section it came from — one claim, many `source:` entries:

```yaml
source:
  - ref: SRC-0007#ir-1-incident-response-policy
  - ref: SRC-0007#ir-2-incident-response-training
  - ref: SRC-0007#ir-3-incident-response-testing
```

That is the whole mechanism for "one claim covers a family". The claim does not list the controls it covers — `/ato-map-controls` has each of those controls cite this claim, and the back-link is derived. References point one way, toward evidence, always.

Where a claim came from an extractor's staging file, record it:

```yaml
derived_from: .ato/staging/SRC-0007-ac-family.yaml
```

`ato validate` then checks the artefact exists and contains the statement — a question a script can answer, where "who wrote this" is one no hook can. It is provenance, not protection: anyone who could fabricate a claim could fabricate a staging file. Omit it for a claim you wrote from reading a section directly; that is equally legitimate and is not flagged.

`state: draft` until the assessor has looked at it. `confidence` is about how clearly the document asserts it, not about whether it is true — a crisp assertion in a badly-out-of-date document is still `high` confidence *as an extraction*.

`method: document-review` normally. If the source was handled ad hoc — the index will say so — use `ad-hoc`, and confidence cannot then exceed `medium`.

### 5. Record the absences

The extractor returns what the document conspicuously does not say. These are not claims — nothing sourced a claim, which is the point. Put them in `notes/absences.md` with their section reference. Several will become RFIs, and some will become risks.

Keep each absence's basis with it. One found by searching carries the method, the target set, the count, and the false-positive check; one found by reading says so. An absence is an assertion about the whole document, and an assessor challenged on it needs to be able to say how it was established — "we searched for these thirteen products across sixty-one sections and found none" survives a review meeting, "it is not mentioned" does not.

### 6. Queue the terms, do not chase them

Undefined terms go to `glossary/unresolved.md`. Any claim that turns on one gets `state: needs-clarification`. Do not stop, and do not guess what the acronym means.

### 7. Put the batch to the assessor

Show the claims as a list — ID, statement, source — and ask which are accurate extractions. Move those to `asserted`. This is a review of *whether the document says this*, not of whether it is true; do not let the conversation drift into assessment yet.

### 8. Commit

```
ato commit --kind extract --summary "SRC-0007: 31 claims"
```

## Guardrails

- A claim with no source is refused by the contract hook. That is the mechanism working — find the reference, never reword the claim to get past it.
- Never merge two assertions into one claim because they are adjacent. Different evidence, different claim.
- Never extract a claim from framework control text, however specific it sounds. "The organisation implements multi-factor authentication" in a requirement box is the catalogue talking.
- If a source is marked `anchors_unavailable`, it has no sections to cite. Do not extract against it — say so, and offer to prepare the document and re-ingest.
- Never report an absence a sub-agent found by searching without its method and its false-positive check. An unaudited negative is an assertion with more words, and it will be wrong in the reassuring direction.
- Never write claims from a truncated extractor result. Partial output looks exactly like complete output once it is in `claims/`.
- Never add a field to a claim to record which controls it covers. Controls cite claims, not the reverse.
- Never write a claim from the interview notes. `notes/system-context.md` has no source and is not a document; it is context, not assertion.
- Never assess a claim here. Whether it is met is `/ato-reconcile-evidence` and `/ato-map-controls`.
