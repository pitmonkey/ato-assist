"""oscal — the ISM catalogue as data the workbench can filter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ato_assist import oscal

CATALOGUE = {
    "framework": "ism",
    "version": "2026.06.18",
    "source": "https://www.cyber.gov.au/ism/oscal",
    "retrieved": "2026-09-02",
    "controls": [
        {
            "id": "ISM-1997",
            "topic": "Cyber security roles / Embedding cyber security",
            "statement": "Cyber security is embedded into risk management practices.",
            "applicability": ["NC", "OS", "P", "S", "TS"],
            "essential_eight": [],
        },
        {
            "id": "ISM-0421",
            "topic": "Guidelines for system hardening / Authentication",
            "statement": "Passphrases used for single-factor authentication are 14 characters.",
            "applicability": ["P", "S", "TS"],
            "essential_eight": ["ML1", "ML2"],
        },
    ],
}


@pytest.fixture
def catalogue(tmp_path: Path) -> Path:
    path = tmp_path / "ism.json"
    path.write_text(json.dumps(CATALOGUE))
    return path


def test_loads_every_control(catalogue: Path) -> None:
    assert len(oscal.load(catalogue).controls) == 2


def test_a_control_carries_its_statement_and_topic(catalogue: Path) -> None:
    control = oscal.load(catalogue).control("ISM-0421")
    assert control is not None
    assert control.statement.startswith("Passphrases")
    assert "Authentication" in control.topic


def test_an_unknown_control_is_none_rather_than_an_error(catalogue: Path) -> None:
    assert oscal.load(catalogue).control("ISM-9999") is None


def test_a_profile_selects_only_the_controls_that_apply(catalogue: Path) -> None:
    selected = oscal.load(catalogue).profile("OFFICIAL:Sensitive")
    assert [control.id for control in selected] == ["ISM-1997"]


def test_the_protected_profile_includes_both(catalogue: Path) -> None:
    assert len(oscal.load(catalogue).profile("PROTECTED")) == 2


def test_an_essential_eight_level_selects_its_controls(catalogue: Path) -> None:
    assert [c.id for c in oscal.load(catalogue).essential_eight("ML1")] == ["ISM-0421"]


def test_an_unknown_marking_selects_nothing_rather_than_everything(catalogue: Path) -> None:
    assert oscal.load(catalogue).profile("COSMIC") == []


def test_a_missing_catalogue_is_reported_clearly(tmp_path: Path) -> None:
    with pytest.raises(oscal.CatalogueError) as excinfo:
        oscal.load(tmp_path / "absent.json")
    assert "refresh-ism-oscal" in str(excinfo.value)


def test_search_finds_controls_by_word(catalogue: Path) -> None:
    hits = oscal.load(catalogue).search("passphrase")
    assert [control.id for control in hits] == ["ISM-0421"]


def test_search_ranks_a_topic_match_below_a_statement_match(catalogue: Path) -> None:
    hits = oscal.load(catalogue).search("cyber security")
    assert hits[0].id == "ISM-1997"


def test_the_vendored_catalogue_is_present_and_loads() -> None:
    """The plugin ships the catalogue so map-controls works with no network."""
    catalogue = oscal.load()
    assert catalogue.framework == "ism"
    assert len(catalogue.controls) > 500
    assert catalogue.control("ISM-0421") is not None


def test_the_profile_vocabulary_is_available_to_callers(catalogue: Path) -> None:
    assert "OFFICIAL:Sensitive" in oscal.load(catalogue).profiles
    assert "PROTECTED" in oscal.load(catalogue).profiles


@pytest.mark.parametrize(
    ("typed", "canonical"),
    [
        ("PROTECTED", "PROTECTED"),
        ("protected", "PROTECTED"),
        ("  Protected  ", "PROTECTED"),
        ("OFFICIAL:Sensitive", "OFFICIAL:Sensitive"),
        ("official: sensitive", "OFFICIAL:Sensitive"),
        ("OFFICIAL : Sensitive", "OFFICIAL:Sensitive"),
        ("top secret", "TOP SECRET"),
    ],
)
def test_a_near_miss_profile_resolves_to_the_canonical_string(
    typed: str, canonical: str
) -> None:
    assert oscal.normalise_profile(typed) == canonical


@pytest.mark.parametrize("typed", ["banana", "", "OFFICIALS", "restricted", None])
def test_a_profile_that_means_nothing_does_not_resolve(typed: str | None) -> None:
    assert oscal.normalise_profile(typed) is None


def test_a_normalised_profile_selects_the_controls_the_exact_string_would(
    catalogue: Path,
) -> None:
    loaded = oscal.load(catalogue)
    resolved = oscal.normalise_profile("protected")
    assert resolved is not None
    assert loaded.profile(resolved) == loaded.profile("PROTECTED")
