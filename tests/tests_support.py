"""Fixture values shared across test modules."""

from pathlib import Path

from ato_assist import repo, scaffold

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
