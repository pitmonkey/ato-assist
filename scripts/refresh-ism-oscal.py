#!/usr/bin/env python3
"""Refresh the vendored ISM catalogue from cyber.gov.au.

The plugin ships a distilled catalogue rather than the 2.5 MB OSCAL document: the
workbench needs the control ID, what it requires, where it sits, and which
classifications and Essential Eight levels it applies to. Everything else in the OSCAL
file is machinery for tools that resolve profiles, which this one does not.

Run this when a new ISM release lands and there is network access:

    python3 scripts/refresh-ism-oscal.py

ISM content is (c) Commonwealth of Australia, licensed CC BY 4.0.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

SOURCE = (
    "https://raw.githubusercontent.com/AustralianCyberSecurityCentre/ism-oscal/main/"
    "ISM_catalog.json"
)
AUTHORITATIVE = "https://www.cyber.gov.au/ism/oscal"
DESTINATION = Path(__file__).resolve().parents[1] / "data" / "ism" / "catalogue.json"


def main() -> int:
    print(f"fetching {SOURCE}")
    with urllib.request.urlopen(SOURCE) as response:  # noqa: S310 - fixed https URL
        raw = response.read()
    catalog = json.loads(raw)["catalog"]

    controls = [_distil(path, control) for path, control in _walk(catalog.get("groups", []))]
    document = {
        "framework": "ism",
        "version": catalog["metadata"].get("version", "unknown"),
        "last_modified": catalog["metadata"].get("last-modified", ""),
        "source": AUTHORITATIVE,
        "mirror": SOURCE,
        "mirror_sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved": datetime.date.today().isoformat(),
        "licence": "CC BY 4.0, (c) Commonwealth of Australia",
        "controls": [control for control in controls if control is not None],
    }
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(
        f"wrote {len(document['controls'])} controls to {DESTINATION} "
        f"(ISM {document['version']}, {DESTINATION.stat().st_size // 1024} KiB)"
    )
    return 0


def _walk(groups: list[dict[str, Any]], path: tuple[str, ...] = ()) -> Any:
    for group in groups:
        here = path + (group.get("title", ""),)
        for control in group.get("controls", []):
            yield here, control
        yield from _walk(group.get("groups", []), here)


def _distil(path: tuple[str, ...], control: dict[str, Any]) -> dict[str, Any] | None:
    if control.get("class") != "ISM-control":
        return None  # principles are guidance, not assessable controls
    props = control.get("props", [])
    parts = control.get("parts", [])
    statement = next(
        (part.get("prose", "") for part in parts if part.get("name") == "statement"), ""
    )
    return {
        "id": control["id"].upper(),
        "topic": " / ".join(part for part in path if part),
        "statement": statement.strip(),
        "applicability": sorted(
            {p["value"] for p in props if p["name"] == "applicability"}
        ),
        "essential_eight": sorted(
            {p["value"] for p in props if p["name"] == "essential-eight-applicability"}
        ),
        "revision": next((p["value"] for p in props if p["name"] == "revision"), ""),
        "updated": next((p["value"] for p in props if p["name"] == "updated"), ""),
    }


if __name__ == "__main__":
    sys.exit(main())
