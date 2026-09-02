"""Differential oracle: miniyaml must agree with real YAML on everything it accepts.

This is what makes not shipping PyYAML safe. PyYAML is a dev dependency and appears
nowhere in the runtime; here it is the reference implementation. Anything miniyaml
rejects is out of the subset by design, so only accepted documents are compared.
"""

from pathlib import Path

import pytest
import yaml

from ato_assist import miniyaml
from ato_assist.frontmatter import split

REPO_ROOT = Path(__file__).resolve().parents[1]

CORPUS = [
    "id: CLM-0042\ntitle: Privileged access requires MFA\n",
    "count: 3\nratio: 0.5\nopen: true\nshut: false\nowner: null\nempty:\n",
    'version: "2025.03.12"\nid: \'3\'\n',
    "data: OFFICIAL:Sensitive\n",
    "tags:\n  - access\n  - identity\n",
    "classification:\n  data: OFFICIAL\n  environment: PROTECTED\n  marking: PROTECTED\n",
    "source:\n  - ref: SRC-0007#anchor\n    locator: p.34\n  - ref: SRC-0011\n",
    "tags: [access, identity]\nargs: {dir: claims, min: 1}\n",
    "args: {dir: rfi, where: {state: open}, date_field: asked_on, max_days: 21}\n",
    "# comment\nid: CLM-0001\n\ntitle: Thing  # trailing\n",
    'ref: "SRC-0007#privileged-access"\n',
    "statement: |\n  Line one.\n  Line two.\nid: CLM-0001\n",
    "statement: >\n  Line one\n  continues.\nid: CLM-0001\n",
    "updated: 2026-09-02\n",
    'updated: "2026-09-02"\n',
    "phases:\n  - id: intake\n    exit_criteria:\n      - check: file_exists\n"
    "        args: {path: notes/system-context.md}\n",
    "includes: []\nexcludes: []\n",
    "ratings:\n  rare: {minor: low, severe: high}\n  likely: {minor: medium, severe: extreme}\n",
    # Prose. An apostrophe mid-word is the single most common thing in an assessment
    # that a naive quote-tracker mistakes for an opening quote.
    "owner: the organisation's security team\n",
    "statement: \"The system's operator asserts it's enforced.\"\n",
    "note: says \"hello\" mid-line\n",
    "tags:\n  - the owner's view\n  - a second item\n",
    "note: the team's view  # trailing comment\n",
    "args: {dir: claims, note: the owner's view}\n",
]


def _repo_documents() -> list[tuple[str, str]]:
    """Every YAML document shipped in the repo: config files and markdown frontmatter."""
    found: list[tuple[str, str]] = []
    for directory in ("config", "templates", "tests/fixtures"):
        base = REPO_ROOT / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix in (".yaml", ".yml"):
                found.append((str(path.relative_to(REPO_ROOT)), path.read_text()))
            elif path.suffix == ".md":
                front, _ = split(path.read_text())
                if front:
                    found.append((str(path.relative_to(REPO_ROOT)), front))
    return found


# Documents real YAML refuses. Being more permissive than the spec is a bug: it produces
# files this plugin calls conformant that no other YAML tool can read. The corpus above
# only ever proved agreement on what both accept, which is the easy half and is how a
# control title carrying a colon got through.
REJECTED = [
    "title: AU-12: OpenShift auditing enabled by default\n",
    "title: ends with a colon:\n",
    "statement: The rule is: quote it\n",
    "id: CLM-0001\n\tbad: tab\n",
    "a: 1\n---\nb: 2\n",
    "base: &anchor\n  a: 1\n",
]


@pytest.mark.parametrize("document", CORPUS, ids=range(len(CORPUS)))
def test_agrees_with_pyyaml_on_the_corpus(document: str) -> None:
    assert miniyaml.loads(document) == yaml.safe_load(document)


@pytest.mark.parametrize("document", REJECTED, ids=range(len(REJECTED)))
def test_refuses_what_real_yaml_refuses(document: str) -> None:
    with pytest.raises(miniyaml.MiniYamlError):
        miniyaml.loads(document)


def test_nothing_this_parser_accepts_is_rejected_by_real_yaml() -> None:
    """The property that matters, over every document the repo ships."""
    for name, text in _repo_documents():
        try:
            miniyaml.loads(text)
        except miniyaml.MiniYamlError:
            continue  # refusing something is always safe; being lax is not
        # Accepted here, so real YAML must accept it too, or the file is unreadable
        # by anything else that follows the contract.
        yaml.safe_load(text), name


def test_agrees_with_pyyaml_on_every_document_shipped_in_the_repo() -> None:
    documents = _repo_documents()
    for name, text in documents:
        assert miniyaml.loads(text) == yaml.safe_load(text), name
