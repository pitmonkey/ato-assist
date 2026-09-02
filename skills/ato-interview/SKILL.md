---
name: ato-interview
description: >
  Use at the start of an ATO assessment, after ato-init and before any document is
  ingested, to interview the assessor about the system they are assessing. Triggers:
  "/ato-interview", "interview me about the system", "grill me on the system", "let's
  capture what I know", a freshly scaffolded assessment with no notes/system-context.md.
  For interviewing about scope on a penetration test use grill-scope instead; this is an
  ATO assessment's system context.
allowed-tools: [Read, Write, Edit, AskUserQuestion]
---

# ato-interview

Gets what the assessor already knows out of their head and onto disk, before the documents arrive and colour it.

This runs **before** ingest on purpose. An assessor who reads the SSP first inherits the SSP's framing; an assessor who writes down their own understanding first can then notice where the document disagrees with it. That disagreement is where the findings are.

## Procedure

### 1. Cover these topics, in this order

One or two rounds each. Push once on a vague answer, then move on — this is an interview, not an interrogation, and a tired assessor gives worse answers than a brief one.

| Topic | What you are actually after |
|---|---|
| What it does day to day | The business process, in the assessor's words. Not the architecture. |
| Who uses it | Which populations, at what privilege, from where, on whose devices. |
| What data it holds | What kinds, whose, how much, how long. This is what makes the classification real rather than a field in a file. |
| The boundary | What is in, what is out, and **every interface across the line**. Push hardest here — an unstated interface is the most common serious finding. |
| What is inherited | What the platform, the host, or another team provides rather than this system. Inheritance is a judgement and will need a claim to argue it. |
| Existing concerns | What the assessor already suspects is wrong, and why. |
| Who to ask | Who answers questions about this system, and how quickly. |

### 2. Push on vagueness, once

"Standard hardening", "the usual monitoring", "it's all in Azure" are not answers. Ask what specifically, or who would know. If the assessor does not know, that is a finding waiting to happen — say so plainly and record it as a hunch, not a fact.

Then move on. Do not ask the same question three ways.

### 3. Keep facts and hunches apart

Write `notes/system-context.md` with two sections, and never blur them:

- **Stated facts** — what the assessor was told, or has seen. Each can later become a claim, once there is a document to cite. Nothing here is a claim yet; it has no source.
- **Assessor's hunches** — what they suspect, expect, or would bet on. These drive where to look. They **never** become claims and never enter `claims/`.

If the assessor says something that is half of each ("I'm fairly sure they use MFA but I haven't seen it"), it is a hunch. The bar for a fact is that someone stated it or you saw it.

### 4. Queue the acronyms as they come up

Every term the assessor uses that is not already defined goes straight into `glossary.md` if they define it on the spot, or `glossary/unresolved.md` if they do not. Do not stop the interview to chase a definition.

### 5. Record what was decided

Anything that shapes the assessment — the framework, a scoping call, an assumption about inheritance — gets a line in `decisions.md`.

### 6. Hand over

Say what to do next: drop the documents into `inbox/` and run `/ato-ingest`. Mention which parts of the context were thin, so the assessor knows what to look for in the documents.

## Guardrails

- **Never fill a gap yourself.** If the assessor does not know what data the system holds, write "unknown" and let it be visible. A plausible guess in `notes/system-context.md` becomes a claim three steps later and nobody remembers it was invented.
- Never read documents during the interview, even if `inbox/` already has them.
- Never promote a hunch to a fact because it sounds confident.
- Do not ask about classification — `/ato-init` has already settled it.
