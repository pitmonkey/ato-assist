# Baseline glossary

Terms every assessment inherits. Per-assessment terms belong in the assessment's own `glossary.md`, which takes precedence over this file where the two disagree.

Each entry gives the expansion, what the term means in an assessment context, and — where a term is routinely confused with another — what it is *not*.

## ATO — Authority to Operate

A formal decision by an authorising officer to accept the residual security risk of operating a system. The assessment produces the evidence for that decision; it does not make it.

Not to be confused with: accreditation (the older term for the same idea in some frameworks), or certification (a statement that controls were assessed, which is an input to the ATO rather than the ATO itself).

## SSP — System Security Plan

The system owner's description of the system and the security controls they assert are in place. It is a set of *claims*, not evidence.

Not to be confused with: evidence. An SSP statement becomes a claim in `claims/`; something that demonstrates the claim is true becomes an entry in `evidence/`.

## ISM — Information Security Manual

The Australian Signals Directorate's control catalogue, published by ASD and available in machine-readable OSCAL form.

Not to be confused with: the Essential Eight, which is a smaller set of mitigation strategies with maturity levels, expressed in the ISM OSCAL release as its own profile.

## IRAP — Infosec Registered Assessors Program

The ASD programme under which endorsed assessors evaluate systems against the ISM. An IRAP assessment is one route to an ATO, not a synonym for it.

## PSPF — Protective Security Policy Framework

The Commonwealth policy framework covering security governance, information, personnel and physical security. The ISM sits under its information security outcome.

## Essential Eight

Eight mitigation strategies with maturity levels ML1–ML3. Often assessed alongside the ISM but scored separately.

## Control

A requirement from a framework catalogue. In this workbench a control has a *status*, and that status must rest on claims and evidence.

Not to be confused with: a claim. A claim is what the system owner says; a control is what the framework requires.

## Claim

A single falsifiable assertion extracted from a source document, carrying a reference back to where it was asserted.

## Evidence

An artefact that bears on a claim — a configuration export, a scan output, a screenshot, an observation — recorded with its provenance and whether it supports, refutes or partly supports the claim.

## RFI — Request for Information

A question put to the system owner or a third party, tracked to closure. An RFI is closed by something landing in `sources/`, not by a verbal answer.

## Residual risk

The risk remaining after existing controls and agreed treatments. It is what the authorising officer accepts.

## Inherited control

A control satisfied by an underlying service or platform rather than by this system. Inheritance is a judgement and must cite the claim that argues it.

## Boundary

What is inside the assessment scope and what is outside it, including every interface across the line. Recorded in `assessment.yaml` under `scope`, with a source reference to the document that authorises it.
