# ato-assist — Repo Guide (for working ON the plugin)

This repo IS the source of the **ato-assist** Claude Code plugin. Editing here changes the plugin's behaviour. It is **not** an assessment workspace — never scaffold an assessment, ingest documents, or store assessment data in this directory.

> Two different `CLAUDE.md` files exist, don't confuse them:
> - **This file** — guides developing the plugin.
> - **`templates/assessment-CLAUDE.md`** — copied by the `ato-init` skill into an assessor's *assessment* repo. That one governs how Claude behaves during a real assessment; edit it deliberately.

## What the plugin does

Turns an empty directory into an ATO (authority to operate) assessment workbench. It owns the directory layout, the file schemas, and the workflow mechanics; the assessor owns every judgement.

Four ideas carry the design:

1. **Contract over capability.** The YAML frontmatter schemas for `sources/ claims/ evidence/ controls/ risks/ rfi/` are the integration API. Anything that writes a conformant file is integrated.
2. **Traceability is mechanical.** A `PreToolUse` hook denies a claim, control or risk that does not cite a source. Not a prompt instruction — a hook.
3. **State lives in files; status is derived.** `ato status` recomputes every number from the files. Nothing about "where we are" is ever written as prose.
4. **Never block; degrade gracefully; record provenance.** No adapter for an input? Handle it ad hoc, label it `method: ad-hoc`, and log the gap. Only genuinely impossible cases produce a stub and a question.

## Layout

```
.claude-plugin/plugin.json      plugin manifest
.claude-plugin/marketplace.json single-plugin marketplace for `/plugin marketplace add`
bin/ato                         PATH shim onto the CLI
src/ato_assist/                 the Python package (see below)
hooks/hooks.json                auto-discovered hook config
hooks/*.py                      thin hook entry points
skills/<name>/SKILL.md          one skill per dir; the dir name is the slash command
agents/<name>.md                subagent definitions
config/                         org defaults copied into an assessment at init
templates/                      files ato-init copies into an assessment repo
data/ism-oscal/<release>/       vendored pinned ISM OSCAL catalog + profiles
scripts/                        maintenance scripts (not shipped behaviour)
tests/                          pytest; every test assessment is built at runtime by `scaffold.create`
```

## Python runtime — no venv, anywhere

**Runtime third-party dependencies are zero, deliberately.** An installed plugin runs against system `python3` with nothing to install:

- Hooks: `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/<script>.py"`, bootstrapping with `sys.path.insert(0, f"{os.environ['CLAUDE_PLUGIN_ROOT']}/src")`.
- CLI: the same interpreter, via the `bin/ato` shim.
- YAML is `miniyaml.py`, ours. Document conversion shells out to `pandoc` / `pdftotext` as external **binaries**, not Python packages. OSCAL is JSON. xlsx is written with `zipfile` + `xml.etree`; csv is the guaranteed path.

The only venv is `.venv` in this repo, development-only, managed by `uv`: pytest, ruff, mypy, and PyYAML as the differential oracle for `miniyaml`. An installed plugin never touches it.

### Hook-safe vs CLI-only

| Hook-safe (stdlib only, no CLI-only imports) | CLI-only |
|---|---|
| `miniyaml` `frontmatter` `schema` `refs` `repo` `validate` `hookio` | `checks` `status` `ingest` `oscal` `risk` `export` `gitops` `scaffold` `cli` |

`test_hook_modules_never_reach_for_a_third_party_package_or_the_cli` in `tests/test_hook_scripts.py` enforces this by inspecting `sys.modules` after a hook bootstrap. It is a **denylist of seven names**, not an allowlist: `yaml`, `cli`, `status`, `checks`, `ingest`, `export`, `scaffold`. A new module — or `oscal`, or `risk` — passes it silently, so it tells you about an import only if the import is on that list.

## Where things are

| Concern | Module |
|---|---|
| YAML subset, frontmatter | `miniyaml` `frontmatter` |
| The contract, and checking it | `schema` `validate` `refs`-in-`validate` |
| Finding and reading an assessment | `repo` (`find_root`, `RepoIndex`) |
| Hook decisions | `hookio`, with thin scripts in `hooks/` |
| Exit criteria, derived status | `checks` `status` `session` |
| Documents in, sources out | `ingest` `glossary` |
| Framework data | `oscal`, catalogue in `data/ism/` |
| Phases and RFIs | `tracking` |
| Ratings, register, report | `risk` `export` `xlsxlite` |
| Commits | `gitops` |

## Conventions

**Authoring skills** (follow `superpowers:writing-skills`):
- Frontmatter `name` (hyphens, matches the directory) + `description`.
- `description` = **triggering conditions only**, no workflow summary — otherwise agents act on the description instead of reading the body. Pack it with concrete trigger phrases and the slash command, and disambiguate against sibling skills.
- Body: purpose line, numbered `## Procedure`, tables for closed vocabularies, closing `## Guardrails`.

**Sub-agent confinement** — `extractor` and `evidence-checker` may write only under `.ato/staging/` and get no shell, enforced by the PreToolUse hook rather than by the agent's `tools:` list. Their output routinely exceeds what a subagent reply can carry (~16 KB, truncated from the end, silently), so they need a write channel; the hook is what keeps that channel from becoming a way into the assessment.

Treat `tools:` and `disallowedTools:` frontmatter as **documentation of intent, never as a control**. Field testing found agents declared `tools: [Read, Grep, Glob]` writing files to disk, and `disallowedTools: Bash` not preventing a shell. Whether that is universal or particular to one harness, a confinement that depends on the declaration being honoured is a confinement that might not be there.

**Measured, on one harness: neither `agent_type` nor `agent_id` is populated on a sub-agent's PreToolUse payload.** A dispatched `extractor` used Bash, wrote to staging, wrote a well-formed claim straight into `claims/`, and wrote to `notes/` — four for four, no code emitted. `ATO-E002` and `ATO-E003` are therefore **inert here**. They are kept because they are correct wherever identity is populated and would have to be rebuilt otherwise, not because they are protecting anything today. Do not describe them as protection without checking the payload first.

The schema gate does still fire on sub-agent writes — the same probe was blocked by `ATO-E101` when the file had no frontmatter. What is missing is only the ability to say who wrote a conformant one.

The honest limit of the hook version: it acts on the identity the payload carries. A named confined agent is scoped; a subagent named only by `agent_id` is refused on the contract directories (`ATO-E003`), because "some subagent" does not answer "who wrote this claim"; a payload with no identity at all is treated as the main conversation. That last case is also what a harness populating nothing looks like — where that is true, the schema gate is all that stands, and it checks a file's shape, not its authorship. Do not describe it as containment.

**Hook scripts** — house envelope, non-negotiable: never raise, never block by accident, always exit 0. The only intentional non-pass outcome is a structured JSON `permissionDecision: "deny"`. Wrap `main()` in `try/except Exception: pass` and `sys.exit(0)`.

**Error codes** — every validator finding carries a stable `ATO-Exxx` code. Codes are greppable and quoted in deny messages; never renumber one.

**Test the direction that can fail.** A check whose corpus is generated by the thing under test can only ever confirm the thing under test. Two examples from this repository, both found in the field rather than by the suite:

- The miniyaml differential oracle proved this parser and PyYAML agree on documents **both accept**. A document one accepts and the other rejects is unreachable from that corpus by construction, so a control title carrying an unquoted colon — accepted here, rejected by PyYAML — went through. The property that matters is the other direction: nothing this parser accepts may be rejected by real YAML.
- A document-preparation adapter verified its output line for line against its input. A section boundary the adapter never recognised is in neither side of that comparison, so the check passed perfectly on a run that lost two appendices.

Both checks were sound, both were named after the property that mattered, and both measured the easy half of it. When writing a check, say out loud what a failure would look like, and confirm the corpus can contain one.

**Verification** — `uv run pytest && uv run ruff check && uv run mypy` before every commit.

**Markdown prose** — one paragraph per line, no hard wrapping.
