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
tests/                          pytest, with committed fixture assessment repos
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

`tests/test_hook_surface.py` enforces this by inspecting `sys.modules` after a hook bootstrap. If you add an import to a hook-safe module, that test tells you.

## Conventions

**Authoring skills** (follow `superpowers:writing-skills`):
- Frontmatter `name` (hyphens, matches the directory) + `description`.
- `description` = **triggering conditions only**, no workflow summary — otherwise agents act on the description instead of reading the body. Pack it with concrete trigger phrases and the slash command, and disambiguate against sibling skills.
- Body: purpose line, numbered `## Procedure`, tables for closed vocabularies, closing `## Guardrails`.

**Hook scripts** — house envelope, non-negotiable: never raise, never block by accident, always exit 0. The only intentional non-pass outcome is a structured JSON `permissionDecision: "deny"`. Wrap `main()` in `try/except Exception: pass` and `sys.exit(0)`.

**Error codes** — every validator finding carries a stable `ATO-Exxx` code. Codes are greppable and quoted in deny messages; never renumber one.

**Verification** — `uv run pytest && uv run ruff check && uv run mypy` before every commit.

**Markdown prose** — one paragraph per line, no hard wrapping.
