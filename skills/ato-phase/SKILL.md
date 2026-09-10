---
name: ato-phase
description: >
  Use when someone asks whether an ATO assessment can move to the next phase, what the current phase requires, or wants to move the phase marker. Triggers: "/ato-phase", "can we move on", "what's left in this phase", "next phase", "are we done with gap analysis". For the whole picture including coverage and RFIs use ato-status; for how an assessment is conducted in general, including phases you are not in, ato-process.
allowed-tools: [Bash, AskUserQuestion]
---

# ato-phase

Shows what the current phase requires, and moves the marker when the assessor says so.

## Procedure

### 1. Show the criteria

```
ato status .
```

The exit criteria block shows each criterion, whether it passes, and which files are failing it. Read the offenders out — "3 sources uncited: SRC-0011, SRC-0019" is actionable; "criteria not met" is not.

### 2. Put the decision to the assessor

If every criterion passes, say so and ask whether to move. If some do not, say which and what would satisfy them, and ask whether to move anyway.

**Moving with criteria unmet is allowed.** The criteria are a checklist, not a gate — an assessor may have a good reason, and a tool that blocks them will simply be worked around. What is not allowed is moving without them saying so.

### 3. Move it

```
ato phase next          # to the following phase
ato phase report        # to a named phase
```

This records the move in `decisions.md`. If the assessor moved with criteria unmet, add a line saying which and why — that is exactly the kind of judgement the decisions log exists for.

### 4. Commit

```
ato commit --kind phase --summary "intake -> claims-extraction"
```

## Guardrails

- **Never move the phase because the criteria pass.** Passing criteria are an invitation to ask, not permission to act.
- Never move backwards without asking why — going back usually means something was found, and that finding should be recorded before the marker moves.
- Never edit `assessment.yaml` by hand to change the phase. Use the command, so the decision is logged.
