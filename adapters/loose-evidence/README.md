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

## The second adapter

Deliberately unwritten. It should cover whichever evidence source the assessment team actually hits most often, and that has not been established yet. Guessing would produce an adapter nobody uses and a shape everyone copies.
