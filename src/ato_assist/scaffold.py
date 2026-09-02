"""Creating an assessment repository.

One assessment, one git repository. The layout, the copied configuration and the initial
commit all happen here so that `/ato-init` is a conversation about classification and
scope rather than about directories.
"""

from __future__ import annotations

import datetime
import subprocess
from pathlib import Path
from typing import Any, NamedTuple

from . import frontmatter
from .repo import ASSESSMENT_FILE
from .schema import MARKINGS, marking_rank

__all__ = ["Spec", "ScaffoldError", "create"]

PLUGIN_ROOT = Path(__file__).resolve().parents[2]

CONTRACT_DIRECTORIES = {
    "sources": "Ingested documents, one directory per document, split by heading. "
               "Written by `/ato-ingest`; each carries an `index.md` with its provenance.",
    "claims": "One discrete assertion per file, extracted from a source and citing it. "
              "A claim with no source is refused by the contract hook.",
    "evidence": "Artefacts bearing on a claim, with provenance and a verdict. "
                "Evidence is primary: it points at its artefact, not at another document.",
    "controls": "Framework control statuses, one directory per framework. "
                "An assessed control cites the claims and evidence its status rests on.",
    "risks": "One risk per file: threat, vulnerability, consequence, rating, treatment. "
             "The rating is derived from `risk-matrix.yaml`, never typed in.",
    "rfi": "Questions put to the customer, tracked to closure. "
           "An RFI is closed by something landing in `sources/`, not by a verbal answer.",
}

OTHER_DIRECTORIES = {
    "inbox": "Drop original documents here, then run `/ato-ingest`. Nothing reads from "
             "this directory except ingest.",
    "notes": "Assessor working notes. Never validated, never a source for a claim.",
    "outputs": "Generated and regenerable: the risk register and the report. "
               "Every file here carries the assessment marking in its header.",
    "glossary": "`unresolved.md` — the queue of terms found in documents and not yet "
                "defined. Resolved one at a time by `/ato-glossary`.",
}


class Spec(NamedTuple):
    name: str
    short_name: str
    owner: str
    assessor: str
    data: str
    environment: str
    marking: str
    framework: str = "ism"
    profile: str = "PROTECTED"
    framework_version: str = "unpinned"
    retain: str = "gitignore"
    retention_days: int = 30
    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()


class ScaffoldError(RuntimeError):
    """The assessment cannot be created as specified."""


def create(root: Path, spec: Spec, today: datetime.date | None = None) -> Path:
    """Scaffold an assessment at ``root``. Refuses rather than overwriting."""
    root = Path(root)
    if (root / ASSESSMENT_FILE).exists():
        raise ScaffoldError(f"{root / ASSESSMENT_FILE} already exists; refusing to overwrite")
    _check_classification(spec)

    for name, purpose in {**CONTRACT_DIRECTORIES, **OTHER_DIRECTORIES}.items():
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        # A README rather than a .gitkeep: an empty directory in an unfamiliar workspace
        # should say what belongs in it.
        (directory / "README.md").write_text(f"# `{name}/`\n\n{purpose}\n")

    # Controls are keyed by framework, because two frameworks have colliding control IDs.
    framework = root / "controls" / spec.framework
    framework.mkdir(parents=True, exist_ok=True)
    (framework / "README.md").write_text(
        f"# `controls/{spec.framework}/`\n\nOne file per {spec.framework} control, named "
        f"by the framework's own ID (`ISM-0421.md`). Written by `/ato-map-controls`.\n"
    )

    (root / ASSESSMENT_FILE).write_text(_assessment_yaml(spec, today or datetime.date.today()))
    _copy_config(root)
    _seed_working_files(root, spec)
    (root / ".gitignore").write_text(_gitignore(spec))
    _git_init(root, spec)
    return root


def _check_classification(spec: Spec) -> None:
    ranks = {
        "data": marking_rank(spec.data),
        "environment": marking_rank(spec.environment),
        "marking": marking_rank(spec.marking),
    }
    for name, rank in ranks.items():
        if rank < 0:
            raise ScaffoldError(
                f"classification.{name} is {getattr(spec, name)!r}, which is not one of: "
                + ", ".join(MARKINGS)
            )
    highest = max(ranks["data"], ranks["environment"])
    if ranks["marking"] < highest:
        raise ScaffoldError(
            f"marking {spec.marking!r} is below {MARKINGS[highest]!r}; assessment artefacts "
            "inherit the highest classification they describe"
        )


def _assessment_yaml(spec: Spec, today: datetime.date) -> str:
    data: dict[str, Any] = {
        "schema": "ato-assist/assessment@1",
        "system": {
            "name": spec.name,
            "short_name": spec.short_name,
            "owner": spec.owner,
            "assessor": spec.assessor,
        },
        "classification": {
            "data": spec.data,
            "environment": spec.environment,
            "marking": spec.marking,
        },
        "scope": {
            "includes": list(spec.includes),
            "excludes": list(spec.excludes),
        },
        "frameworks": [
            {"id": spec.framework, "version": spec.framework_version, "profile": spec.profile}
        ],
        "phase": "intake",
        "inbox": {"retain": spec.retain, "retention_days": spec.retention_days},
        "created": today,
    }
    return frontmatter.dump(data)


def _copy_config(root: Path) -> None:
    for name in ("process.yaml", "risk-matrix.yaml", "register-columns.yaml"):
        (root / name).write_text((PLUGIN_ROOT / "config" / name).read_text())


def _seed_working_files(root: Path, spec: Spec) -> None:
    templates = PLUGIN_ROOT / "templates"
    workspace = (templates / "assessment-CLAUDE.md").read_text()
    (root / "CLAUDE.md").write_text(
        workspace.replace("{system_name}", spec.name).replace("{marking}", spec.marking)
    )
    for template, destination in (
        ("decisions.md", "decisions.md"),
        ("tooling-gaps.md", "tooling-gaps.md"),
        ("glossary.md", "glossary.md"),
        ("glossary-unresolved.md", "glossary/unresolved.md"),
    ):
        (root / destination).write_text((templates / template).read_text())


def _gitignore(spec: Spec) -> str:
    lines = [
        "# Session bookkeeping: local to this machine, never shared.",
        ".ato/",
        "",
        "__pycache__/",
        ".DS_Store",
        "",
    ]
    if spec.retain == "gitignore":
        lines += [
            "# Original documents stay on disk but out of git: they are the customer's,",
            "# often large, and often more sensitive than the extraction. `sources/` and the",
            "# ingest manifest carry the traceability.",
            "inbox/*",
            "!inbox/README.md",
            "",
        ]
    return "\n".join(lines)


def _git_init(root: Path, spec: Spec) -> None:
    if not (root / ".git").is_dir():
        _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"init: {spec.name} assessment ({spec.marking})")


def _git(root: Path, *args: str) -> None:
    try:
        subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ScaffoldError(f"git {' '.join(args)} failed: {exc}") from exc
