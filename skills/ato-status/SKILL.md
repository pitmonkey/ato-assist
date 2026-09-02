---
name: ato-status
description: >
  Use when someone asks where an ATO assessment stands, what is blocking the current
  phase, what is outstanding, or what changed since last time. Triggers: "/ato-status",
  "where are we", "what's left", "what's blocking", "how's the assessment going",
  "catch me up", returning to an assessment after time away. For the exit criteria of a
  phase and moving the marker use ato-phase; this is the whole picture.
allowed-tools: [Bash]
---

# ato-status

Shows where the assessment stands. Every number is recomputed from the files.

## Procedure

```
ato status .
```

Print what it returns. Do not summarise it, reformat it, or add a narrative around it — it is already one screen, and a second account of the same thing is a second thing to go stale.

Add one sentence only if something in the output needs acting on now:

- A criterion failing with named offenders — say which file to open first.
- An RFI marked `!` (over 21 days) — say who it is with.
- A placeholder configuration still flagged — say it must be validated before anything reaches a governance board.

## Guardrails

- **Never write a status paragraph anywhere.** Not in `notes/`, not in `decisions.md`, not in a comment. Status is derived; a written one is immediately wrong.
- Never move the phase marker because the criteria pass. Only the assessor moves it, through `/ato-phase next`.
- If `ato status` reports the assessment as unreadable, that is the finding. Show the YAML error and stop; do not attempt to repair `assessment.yaml` without asking.
