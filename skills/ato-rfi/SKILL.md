---
name: ato-rfi
description: >
  Use when an ATO assessment needs something from the customer that the documents do not
  answer, when an answer has arrived and a question can be closed, or when the open
  questions need sending as a message. Triggers: "/ato-rfi", "raise an RFI", "ask the
  customer", "what are we waiting on", "send the outstanding questions", "they've sent
  the diagram". To record what arrives as a source use ato-ingest.
allowed-tools: [Bash, Read, AskUserQuestion]
---

# ato-rfi

Tracks what the assessment is waiting on, and who it is waiting on.

## Procedure

### Raising one

```
ato rfi new --question "<the question>" --asked-of "<who>" --reason <CLM-|ISM-|RSK- id>
```

Write the question so it can be answered without a conversation. "Please provide the current conditional access policy export" is answerable; "can you tell us about MFA" is not, and will come back as a meeting.

`--reason` records what this unblocks. It is what makes an RFI more than a to-do: the status screen can then show what is stuck behind it.

Raise one when the answer is genuinely not in the documents. Not when it is in a document you have not read — check `sources/` first.

**The first round is already written.** `notes/system-context.md` carries a `## Open questions` checklist from the interview, and `ato status` counts what is still unticked. Anything on it that ingest did not answer is an RFI waiting to be raised — start there rather than inventing questions.

### Closing one

```
ato rfi close RFI-0003 --source SRC-0011
```

**An RFI closes because something landed in `sources/`.** A verbal answer in a meeting is a hunch until it is written down; if the customer answered in an email, ingest the email. The command refuses to close without a source, and that refusal is the point.

### Listing and sending

```
ato rfi list       # what is open, and with whom
ato rfi export     # the message, ready to send
```

The exported message carries the assessment marking. Read it before sending: it leaves the assessment, so the marking on it is a real classification decision, not a header.

### After any change

```
ato commit --kind rfi --summary "RFI-0003 closed by customer response"
```

## Ageing

`ato status` flags anything open past 21 days. When something ages out, put it to the assessor as a decision: chase it, escalate it, or assess without it and record the gap as a risk. Do not let it sit.

## Guardrails

- Never close an RFI on your own judgement, and never because the answer seems obvious.
- Never batch unrelated questions into one RFI. One question, one ID, one thing to close.
- Never raise an RFI for something a document already answers.
- Do not soften a question to make it easier to ask. An assessment that gets a comfortable answer to a vague question has learned nothing.
