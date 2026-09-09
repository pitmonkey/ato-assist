"""Fixture values shared across test modules."""

import datetime
from pathlib import Path

from ato_assist import frontmatter, repo, scaffold

PLUGIN_ROOT = Path(__file__).resolve().parents[1]

SPEC = scaffold.Spec(
    name="Example System",
    short_name="exs",
    owner="business.owner@agency.gov.au",
    assessor="pete",
    data="OFFICIAL:Sensitive",
    environment="PROTECTED",
    marking="PROTECTED",
)


def ism_vocabularies() -> repo.Vocabularies:
    """The shipped ISM vocabulary, through the real loader.

    Loading what actually ships rather than a Python mirror of it is what makes a test
    asserting `alternate-control` is accepted an assertion about the plugin.
    """
    return repo.load_vocabularies(PLUGIN_ROOT / "config" / "frameworks")


def control(
    root: Path,
    identifier: str = "ISM-0421",
    *,
    status: str = "effective",
    framework: str = "ism",
    updated: str | datetime.date = "2026-09-02",
    **overrides: object,
) -> Path:
    """Write one conformant control file."""
    directory = root / "controls" / framework
    directory.mkdir(parents=True, exist_ok=True)
    fields: dict[str, object] = {
        "id": identifier,
        "framework": framework,
        "title": "A control",
        "status": status,
        "claims": ["CLM-0001"],
        "confidence": "medium",
        "method": "document-review",
        "updated": updated,
    }
    fields.update(overrides)
    path = directory / f"{identifier}.md"
    path.write_text(frontmatter.render(fields, ""))
    return path
