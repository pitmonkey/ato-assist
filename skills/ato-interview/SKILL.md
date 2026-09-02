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

### 2. When the assessor does not know

Two or three consecutive "don't know" answers means the assumption behind this interview has failed. A consultant handed someone else's SSP has no prior knowledge of the system by definition, so this is common rather than exceptional. **Stop working through the remaining topics one at a time.** An assessor being asked seven questions they cannot answer gives worse answers to the two they can.

Say so plainly — "you're working cold on this one, so let me ask it differently" — and switch the frame:

| Instead of | Ask |
|---|---|
| What data does it hold? | What data would you expect a system like this to hold? |
| What is across the boundary? | What interfaces would you expect to find, and which would worry you? |
| What is inherited? | What would you expect the platform to provide rather than this system? |
| What are your concerns? | What would you go looking for first? |

An assessor with no facts still has expectations, and expectations are the whole reason for interviewing before ingest: they are what the document can then disagree with. "I'd expect a platform like this to have an image registry and an identity provider" is worth recording — if the document never mentions either, that is a finding. A page of "unknown" gives you nothing to compare against.

Expectations are **hunches**. They go under `## Assessor's hunches`, never under stated facts, however confident they sound.

Ask the remaining topics as one batch in this mode, not one at a time.

### 3. Push on vagueness, once

"Standard hardening", "the usual monitoring", "it's all in Azure" are not answers. Ask what specifically, or who would know. If the assessor does not know, that is a finding waiting to happen — say so plainly and record it as a hunch, not a fact.

Then move on. Do not ask the same question three ways.

### 4. Keep facts and hunches apart

Write `notes/system-context.md` with two sections, and never blur them:

- **Stated facts** — what the assessor was told, or has seen. Each can later become a claim, once there is a document to cite. Nothing here is a claim yet; it has no source.
- **Assessor's hunches** — what they suspect, expect, or would bet on. These drive where to look. They **never** become claims and never enter `claims/`.

If the assessor says something that is half of each ("I'm fairly sure they use MFA but I haven't seen it"), it is a hunch. The bar for a fact is that someone stated it or you saw it.

### 5. Queue the acronyms as they come up

Every term the assessor uses that is not already defined goes straight into `glossary.md` if they define it on the spot, or `glossary/unresolved.md` if they do not. Do not stop the interview to chase a definition.

### 6. Record what was decided

Anything that shapes the assessment — the framework, a scoping call, an assumption about inheritance — gets a line in `decisions.md`.

### 7. Write the open questions as a checklist

Everything the assessor could not answer goes in `notes/system-context.md` under this exact heading, one unticked box each:

```markdown
## Open questions

- [ ] What data does the platform hold, and whose?
- [ ] What sits across the authorisation boundary?
- [ ] Which controls are inherited from the hosting platform?
```

The heading and the `- [ ]` form matter: `ato status` counts the unticked ones and keeps saying so until the list is empty. This is the seed list for the first round of RFIs.

**Nothing ticks a box on its own.** After ingest, whether a document actually answers a question is a judgement — read the relevant section, decide with the assessor, then tick it. Anything still unticked once the documents are in becomes an RFI:

```
ato rfi new --question "<the question>" --asked-of "<who>"
```

### 8. Hand over

Say what to do next: drop the documents into `inbox/` and run `/ato-ingest`. Read the open questions back, because that list is what ingest is hunting for.

Where the assessor worked cold, say so plainly: the picture came from expectations rather than knowledge, and the documents are being read to test it, not to confirm it.

## Guardrails

- **Never fill a gap yourself.** If the assessor does not know what data the system holds, write "unknown" and let it be visible. A plausible guess in `notes/system-context.md` becomes a claim three steps later and nobody remembers it was invented.
- Never read documents during the interview, even if `inbox/` already has them.
- Never promote a hunch to a fact because it sounds confident. An expectation offered by an experienced assessor is still an expectation.
- Never tick an open question yourself because a document mentions the topic. Mentioning is not answering.
- Do not ask about classification — `/ato-init` has already settled it.
