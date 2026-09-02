"""The ISM catalogue as data.

Control text is never written into a skill. A skill that recites a control drifts from
the framework the moment ASD revises it, and nobody notices. `scripts/refresh-ism-oscal.py`
regenerates this catalogue from cyber.gov.au; everything here just reads it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

__all__ = [
    "Catalogue",
    "CatalogueError",
    "Control",
    "PROFILES",
    "load",
    "normalise_profile",
]

VENDORED = Path(__file__).resolve().parents[2] / "data" / "ism" / "catalogue.json"

# The ISM expresses applicability as a code per classification. A profile IS a
# classification marking, spelled exactly — which is a footgun, because a profile that is
# not in this table selects nothing and looks identical to one that legitimately matches
# no controls. `normalise_profile` exists so callers can tell those two apart.
_APPLICABILITY = {
    "UNOFFICIAL": "NC",
    "OFFICIAL": "NC",
    "OFFICIAL:Sensitive": "OS",
    "PROTECTED": "P",
    "SECRET": "S",
    "TOP SECRET": "TS",
}

PROFILES = tuple(_APPLICABILITY)


def normalise_profile(value: object) -> str | None:
    """The canonical profile a typed value means, or ``None`` if it means nothing.

    Forgiving about typing, strict about meaning: case and whitespace around the colon
    are noise an assessor should not have to get right, but anything that does not
    resolve to a real profile is rejected by the caller rather than quietly selecting no
    controls.
    """
    if not isinstance(value, str):
        return None
    collapsed = " ".join(value.split()).replace(" :", ":").replace(": ", ":")
    for profile in PROFILES:
        if collapsed.casefold() == profile.casefold():
            return profile
    return None


class CatalogueError(RuntimeError):
    """The catalogue is missing or unreadable."""


class Control(NamedTuple):
    id: str
    topic: str
    statement: str
    applicability: tuple[str, ...]
    essential_eight: tuple[str, ...]

    @property
    def title(self) -> str:
        """A short title, taken from the first sentence of what the control requires."""
        first = self.statement.split(". ")[0].strip().rstrip(".")
        return first if len(first) <= 100 else first[:99] + "…"


class Catalogue(NamedTuple):
    framework: str
    version: str
    source: str
    retrieved: str
    controls: tuple[Control, ...]

    def control(self, identifier: str) -> Control | None:
        wanted = identifier.upper()
        return next((c for c in self.controls if c.id == wanted), None)

    @property
    def profiles(self) -> tuple[str, ...]:
        """The profile vocabulary, so a caller can reject an unknown one by name."""
        return PROFILES

    def profile(self, marking: str) -> list[Control]:
        """The controls that apply at a classification.

        An unknown marking selects nothing. Callers that need to distinguish "unknown"
        from "genuinely empty" must ask `normalise_profile` first.
        """
        code = _APPLICABILITY.get(marking)
        return [c for c in self.controls if code and code in c.applicability]

    def essential_eight(self, level: str) -> list[Control]:
        return [c for c in self.controls if level in c.essential_eight]

    def search(self, text: str) -> list[Control]:
        """Controls mentioning ``text``, statement matches first.

        A crude ranking on purpose: this narrows 1,100 controls to a handful for a human
        or a sub-agent to judge. It is not the mapping.
        """
        needle = text.lower()
        in_statement = [c for c in self.controls if needle in c.statement.lower()]
        in_topic = [
            c for c in self.controls if needle in c.topic.lower() and c not in in_statement
        ]
        return in_statement + in_topic


def load(path: Path | str | None = None) -> Catalogue:
    """Read a catalogue, defaulting to the one vendored with the plugin."""
    source = Path(path) if path is not None else VENDORED
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogueError(
            f"no ISM catalogue at {source}. Run `python3 scripts/refresh-ism-oscal.py` "
            "on a machine with network access."
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogueError(f"{source} is unreadable: {exc}") from exc

    return Catalogue(
        framework=document.get("framework", "ism"),
        version=document.get("version", "unknown"),
        source=document.get("source", ""),
        retrieved=document.get("retrieved", ""),
        controls=tuple(
            Control(
                id=entry["id"],
                topic=entry.get("topic", ""),
                statement=entry.get("statement", ""),
                applicability=tuple(entry.get("applicability", ())),
                essential_eight=tuple(entry.get("essential_eight", ())),
            )
            for entry in document.get("controls", [])
        ),
    )
