"""The ISM catalogue as data.

Control text is never written into a skill. A skill that recites a control drifts from
the framework the moment ASD revises it, and nobody notices. `scripts/refresh-ism-oscal.py`
regenerates this catalogue from cyber.gov.au; everything here just reads it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

__all__ = ["Catalogue", "CatalogueError", "Control", "load"]

VENDORED = Path(__file__).resolve().parents[2] / "data" / "ism" / "catalogue.json"

# The ISM expresses applicability as a code per classification.
_APPLICABILITY = {
    "UNOFFICIAL": "NC",
    "OFFICIAL": "NC",
    "OFFICIAL:Sensitive": "OS",
    "PROTECTED": "P",
    "SECRET": "S",
    "TOP SECRET": "TS",
}


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

    def profile(self, marking: str) -> list[Control]:
        """The controls that apply at a classification."""
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
