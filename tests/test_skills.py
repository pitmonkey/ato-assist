"""The skill files, and the two pages that index them.

`ato-help` lists every skill and `ato-process` maps every phase onto the skills that do
it. Both are prose naming things that live elsewhere, so both rot silently when a skill is
added or renamed. These check the direction that actually fails: something changed in the
repository and the page describing it did not.
"""

from __future__ import annotations

import re
from pathlib import Path

from ato_assist import frontmatter, miniyaml

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS = PLUGIN_ROOT / "skills"

# A skill is named by its slash command wherever either page refers to one.
_COMMAND = re.compile(r"`/(ato-[a-z0-9-]+)`")


def skill_dirs() -> list[str]:
    return sorted(path.name for path in SKILLS.iterdir() if path.is_dir())


def body_of(skill: str) -> str:
    _, body = frontmatter.split((SKILLS / skill / "SKILL.md").read_text(encoding="utf-8"))
    return body


def phase_table() -> list[tuple[str, str]]:
    """The `## Phases` table in ato-process, as (phase id, skills cell) in file order."""
    section = body_of("ato-process").split("## Phases", 1)[1]
    rows: list[tuple[str, str]] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            if rows:
                break  # The table has ended; anything later is a different table.
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        phase = re.fullmatch(r"`([a-z-]+)`", cells[0])
        if phase:
            rows.append((phase.group(1), cells[-1]))
    return rows


def test_every_skill_is_named_by_its_own_directory() -> None:
    # Read with a regex, not miniyaml: a SKILL.md is parsed by Claude Code's own YAML, not
    # by ours, and a folded description spanning a quoted phrase is valid there and outside
    # our subset. What matters is only that the two names agree.
    for skill in skill_dirs():
        path = SKILLS / skill / "SKILL.md"
        assert path.is_file(), f"{skill} has no SKILL.md"
        front, _ = frontmatter.split(path.read_text(encoding="utf-8"))
        assert front is not None, f"{skill} has no frontmatter"
        declared = re.search(r"^name:\s*(\S+)\s*$", front, re.MULTILINE)
        assert declared is not None, f"{skill} declares no name"
        assert declared.group(1) == skill, f"{skill} declares name: {declared.group(1)}"
        assert re.search(r"^description:\s*\S", front, re.MULTILINE), (
            f"{skill} has no description"
        )


def test_ato_help_indexes_every_skill() -> None:
    listed = set(_COMMAND.findall(body_of("ato-help")))
    missing = sorted(set(skill_dirs()) - listed)
    assert not missing, f"skills missing from the /ato-help index: {missing}"


def test_the_phase_table_names_only_skills_that_exist() -> None:
    named = {skill for _, cell in phase_table() for skill in _COMMAND.findall(cell)}
    unknown = sorted(named - set(skill_dirs()))
    assert not unknown, f"/ato-process names skills that do not exist: {unknown}"


def test_the_phase_table_matches_the_shipped_process() -> None:
    shipped = miniyaml.loads((PLUGIN_ROOT / "config" / "process.yaml").read_text("utf-8"))
    expected = [phase["id"] for phase in shipped["phases"]]
    assert [phase for phase, _ in phase_table()] == expected


def test_every_phase_has_a_skills_column_that_says_something() -> None:
    # A phase no skill serves is a finding, not a blank cell — ato-process says so for
    # threat-mapping. An empty cell here would read as an oversight instead.
    for phase, cell in phase_table():
        assert cell, f"{phase} has an empty skills cell"
