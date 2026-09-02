# ato-loose-evidence

The reference adapter for [ato-assist](../../README.md).

It takes an arbitrary file and a one-line description from the assessor and writes a conformant entry into an assessment's `evidence/` directory. That is all an adapter is.

It exists to demonstrate the integration model: **the file contract is the whole API**. Anything that writes a conformant file into `evidence/` is integrated — another plugin, a shell script, a person with an editor. There is nothing to register with and nothing to import.

Domain-specific evidence analysis — cloud telemetry, vulnerability scans, log interpretation — belongs in adapters like this one, never in `ato-assist` itself.

## Install

```
/plugin marketplace add pitmonkey/ato-assist
/plugin install ato-loose-evidence@ato-assist
```

## If you write a document-preparation adapter

A structure-recognising adapter — one that promotes numbered sections or control identifiers to headings in a document Word produced without heading styles — needs **two** verification gates, and the obvious one is not enough.

The first gate is text preservation: identical line count, no line differing except by an added prefix. That proves the adapter changed nothing it should not have.

The second gate is the one that gets missed: **no title-like line may remain unpromoted in the body of a section.** A text-preservation check is structurally blind by construction — it compares output to input line for line, so a boundary the adapter never recognised is invisible to it and the check passes perfectly.

This is not hypothetical. An adapter that recognised numbered sections, subsections and control identifiers, and verified its output line for line, silently absorbed two appendices into the section above them. One of those appendices was an attachment inventory recording that five artefacts the assessment had raised requests for information about had in fact been provided. The verification held; the document was still wrong.

Build the second gate in from the start. An adapter that only proves it preserved the text has proved the easy half.

## The second adapter

Deliberately unwritten. It should cover whichever evidence source the assessment team actually hits most often, and that has not been established yet. Guessing would produce an adapter nobody uses and a shape everyone copies.
