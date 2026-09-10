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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("note: |\n  code # not a comment\n", "code # not a comment\n"),
        ("note: >\n  the organisation's\n  policy\n", "the organisation's policy\n"),
        ('note: >\n  she said "hello\n  there"\n', 'she said "hello there"\n'),
        ("note: |\n  ---\n  after\n", "---\nafter\n"),
        ("note: |\n  has\ta tab\n", "has\ta tab\n"),
        ("note: |\n  \tcontent\n  more\n", "\tcontent\nmore\n"),
        ("note: |\n  title: AU-12: OpenShift\n", "title: AU-12: OpenShift\n"),
    ],
)
def test_a_block_scalar_body_is_text_not_yaml(text: str, expected: str) -> None:
    """Each body carries something the scanner rejects everywhere else.

    A folded `description:` that breaks a quoted phrase across two lines is the case that
    found this: eleven of the plugin's own SKILL.md files were unparseable here while real
    YAML read them fine.
    """
    assert miniyaml.loads(text) == {"note": expected}


def test_a_tab_in_place_of_indentation_is_still_refused() -> None:
    # The body skip must not turn the whole file into text; real YAML refuses this too.
    with pytest.raises(miniyaml.MiniYamlError):
        miniyaml.loads("note: |\n\tcontent\n")


def test_a_block_scalar_chomps_its_trailing_newline_when_told_to() -> None:
    assert miniyaml.loads("note: |-\n  no trailing newline\n") == {
        "note": "no trailing newline"
    }
    assert miniyaml.loads("note: >-\n  folded\n  tight\n") == {"note": "folded tight"}


def test_a_blank_line_inside_a_block_scalar_survives() -> None:
    assert miniyaml.loads("note: |\n  one\n\n  two\n") == {"note": "one\n\ntwo\n"}


def test_a_block_scalar_can_be_the_last_key() -> None:
    assert miniyaml.loads("id: CLM-0001\nnote: |\n  last\n") == {
        "id": "CLM-0001",
        "note": "last\n",
    }


def test_a_block_scalar_inside_a_sequence_item() -> None:
    text = "source:\n  - ref: SRC-0007\n    note: |\n      inside\n"
    assert miniyaml.loads(text) == {"source": [{"ref": "SRC-0007", "note": "inside\n"}]}


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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("owner: the organisation's security team\n", "the organisation's security team"),
        ("note: it's fine\n", "it's fine"),
        ("note: says \"hello\" mid-line\n", 'says "hello" mid-line'),
        ("note: two apostrophes: none\n", None),  # a colon still ends the key
    ],
)
def test_an_apostrophe_inside_a_word_is_not_a_quoted_scalar(
    text: str, expected: str | None
) -> None:
    """A quote character only opens a scalar at the start of one.

    `the organisation's policy` is ordinary prose and extremely common in an assessment;
    reading the apostrophe as an opening quote made the whole file unparseable.
    """
    if expected is None:
        with pytest.raises(miniyaml.MiniYamlError):
            miniyaml.loads(text)
    else:
        assert list(miniyaml.loads(text).values()) == [expected]


def test_a_quoted_scalar_still_works_after_a_key() -> None:
    assert miniyaml.loads("note: 'properly quoted'\n") == {"note": "properly quoted"}


def test_an_apostrophe_does_not_hide_a_comment() -> None:
    assert miniyaml.loads("note: the team's view  # trailing\n") == {
        "note": "the team's view"
    }


def test_an_apostrophe_in_a_list_item_is_prose() -> None:
    assert miniyaml.loads("tags:\n  - the owner's view\n") == {"tags": ["the owner's view"]}
