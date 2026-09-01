---
name: ato-glossary
description: >
  Use when an ATO assessment has terms queued in glossary/unresolved.md and the assessor
  is ready to define them, or when an item is marked needs-clarification because a term
  is undefined. Triggers: "/ato-glossary", "resolve the glossary", "what does this
  acronym mean", "define the queued terms", "unresolved terms". Terms are queued by
  ato-ingest; this skill empties that queue.
allowed-tools: [Bash, Read, Edit, Write, AskUserQuestion]
---

# ato-glossary

Empties the queue of undefined terms, one at a time, with the context in front of the assessor.

## Procedure

### 1. Read the queue

`glossary/unresolved.md` holds each term with how often it appeared, where it was first seen, and a sample sentence. Work in the order the file gives — most frequent first, because those block the most.

### 2. Walk them one at a time

For each term, show the assessor the term, the count, and the sample sentence. Ask what it means **here** — not what the acronym generally expands to. The same three letters mean different things in different systems, and guessing the common expansion is how an assessment ends up confidently wrong.

Offer a candidate expansion only when the sample sentence makes it unambiguous, and mark it as a guess when you do.

### 3. Write the entry

Append to `glossary.md`:

```markdown
## TERM — Expansion

What it means in this system, in one or two sentences.

Not to be confused with: <the thing it is routinely confused with, and why>.
```

The "not to be confused with" line is not decoration. Most glossary failures in an assessment are collisions — two things that share an acronym, or a term that means something narrower here than in the framework. If there is genuinely nothing to confuse it with, leave the line out rather than inventing one.

### 4. Remove it from the queue

Delete the row from `glossary/unresolved.md` once it is defined.

### 5. Unblock what was waiting

Anything marked `needs-clarification` because of a term you just defined can now be revisited. List those items for the assessor; do not silently change their state.

### 6. Stop when the assessor tires

This is a batch job and it is tedious. After five or six terms, offer to stop and pick up later. A half-empty queue is fine; a rushed definition is not.

## Guardrails

- Never define a term from general knowledge alone. The assessment's meaning is what matters.
- Never delete a queued term without defining it. If it turns out to be noise — a false positive from the acronym scan — say so in the glossary as a one-line "not a term here" entry, so the next ingest does not re-queue it.
- Never expand an acronym inside a claim's `statement`. The statement records what the document said.
