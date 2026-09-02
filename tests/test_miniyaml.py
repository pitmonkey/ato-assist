"""miniyaml — the restricted YAML subset the hooks and the CLI share.

Every test here has a matching differential-oracle case in test_miniyaml_oracle.py;
these assert the shape we want, the oracle asserts we agree with real YAML.
"""

import pytest

from ato_assist import miniyaml


def test_parses_a_flat_block_map_of_strings() -> None:
    assert miniyaml.loads("id: CLM-0042\ntitle: Privileged access\n") == {
        "id": "CLM-0042",
        "title": "Privileged access",
    }


def test_parses_integers_floats_booleans_and_null() -> None:
    text = "count: 3\nratio: 0.5\nopen: true\nshut: false\nowner: null\nempty:\n"
    assert miniyaml.loads(text) == {
        "count": 3,
        "ratio": 0.5,
        "open": True,
        "shut": False,
        "owner": None,
        "empty": None,
    }


def test_quoted_scalars_keep_their_string_type() -> None:
    assert miniyaml.loads('version: "2025.03.12"\nid: \'3\'\n') == {
        "version": "2025.03.12",
        "id": "3",
    }


def test_a_colon_inside_a_bare_scalar_is_kept() -> None:
    assert miniyaml.loads("data: OFFICIAL:Sensitive\n") == {"data": "OFFICIAL:Sensitive"}


def test_parses_a_block_sequence_of_scalars() -> None:
    assert miniyaml.loads("tags:\n  - access\n  - identity\n") == {
        "tags": ["access", "identity"]
    }


def test_parses_a_nested_block_map() -> None:
    text = "classification:\n  data: OFFICIAL\n  marking: PROTECTED\n"
    assert miniyaml.loads(text) == {
        "classification": {"data": "OFFICIAL", "marking": "PROTECTED"}
    }


def test_parses_a_sequence_of_maps() -> None:
    text = "source:\n  - ref: SRC-0007#anchor\n    locator: p.34\n  - ref: SRC-0011\n"
    assert miniyaml.loads(text) == {
        "source": [
            {"ref": "SRC-0007#anchor", "locator": "p.34"},
            {"ref": "SRC-0011"},
        ]
    }


def test_parses_inline_sequences_and_maps() -> None:
    text = "tags: [access, identity]\nargs: {dir: claims, min: 1}\n"
    assert miniyaml.loads(text) == {
        "tags": ["access", "identity"],
        "args": {"dir": "claims", "min": 1},
    }


def test_ignores_comments_and_blank_lines() -> None:
    text = "# leading comment\nid: CLM-0001\n\ntitle: Thing  # trailing\n"
    assert miniyaml.loads(text) == {"id": "CLM-0001", "title": "Thing"}


def test_a_hash_inside_a_quoted_scalar_is_not_a_comment() -> None:
    assert miniyaml.loads('ref: "SRC-0007#privileged-access"\n') == {
        "ref": "SRC-0007#privileged-access"
    }


def test_an_unquoted_ref_keeps_its_anchor() -> None:
    assert miniyaml.loads("ref: SRC-0007#privileged-access\n") == {
        "ref": "SRC-0007#privileged-access"
    }


def test_parses_a_literal_block_scalar() -> None:
    text = "statement: |\n  Line one.\n  Line two.\nid: CLM-0001\n"
    assert miniyaml.loads(text) == {
        "statement": "Line one.\nLine two.\n",
        "id": "CLM-0001",
    }


def test_parses_a_folded_block_scalar() -> None:
    text = "statement: >\n  Line one\n  continues.\nid: CLM-0001\n"
    assert miniyaml.loads(text) == {
        "statement": "Line one continues.\n",
        "id": "CLM-0001",
    }


def test_an_empty_document_is_an_empty_mapping() -> None:
    assert miniyaml.loads("") == {}
    assert miniyaml.loads("\n# only a comment\n") == {}


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("id: CLM-0001\n\ttitle: tabbed\n", "tab"),
        ("base: &anchor\n  a: 1\n", "anchor"),
        ("a: 1\n---\nb: 2\n", "document"),
        ("when: !!timestamp 2026-01-01\n", "tag"),
        ("- just\n- a list\n", "mapping"),
        ("id CLM-0001\n", "expected"),
    ],
)
def test_rejects_constructs_outside_the_subset(text: str, fragment: str) -> None:
    with pytest.raises(miniyaml.MiniYamlError) as excinfo:
        miniyaml.loads(text)
    assert fragment in str(excinfo.value).lower()


def test_the_error_carries_the_line_number() -> None:
    with pytest.raises(miniyaml.MiniYamlError) as excinfo:
        miniyaml.loads("id: CLM-0001\ntitle: ok\n\tbad: tabbed\n")
    assert excinfo.value.line == 3


def test_an_iso_date_becomes_a_date_object_as_in_yaml() -> None:
    import datetime

    assert miniyaml.loads("updated: 2026-09-02\n") == {
        "updated": datetime.date(2026, 9, 2)
    }


def test_a_quoted_iso_date_stays_a_string() -> None:
    assert miniyaml.loads('updated: "2026-09-02"\n') == {"updated": "2026-09-02"}


def test_rejects_ambiguous_boolean_like_scalars() -> None:
    with pytest.raises(miniyaml.MiniYamlError) as excinfo:
        miniyaml.loads("retain: yes\n")
    assert "ambiguous" in str(excinfo.value).lower()


@pytest.mark.parametrize(
    "text",
    [
        "title: AU-12: OpenShift auditing enabled by default\n",
        "title: ends with a colon:\n",
        "statement: The rule is: quote it\n",
        "  - ref: SRC-0001\n    quote: He said: hello\n",
    ],
)
def test_rejects_a_plain_scalar_that_real_yaml_would_reject(text: str) -> None:
    """Being more permissive than YAML is a bug, not a kindness.

    A file this parser accepts and PyYAML rejects is a file the contract calls
    integrable and no other tool can read.
    """
    with pytest.raises(miniyaml.MiniYamlError) as excinfo:
        miniyaml.loads("root:\n" + text if text.startswith(" ") else text)
    assert "quote" in str(excinfo.value).lower()


@pytest.mark.parametrize(
    "text",
    [
        "data: OFFICIAL:Sensitive\n",
        'title: "AU-12: quoted is fine"\n',
        "title: 'AU-12: single quotes too'\n",
        "ref: SRC-0007#anchor\n",
        "url: https://example.gov.au/ism\n",
    ],
)
def test_still_accepts_a_colon_that_real_yaml_accepts(text: str) -> None:
    assert miniyaml.loads(text)
