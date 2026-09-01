"""frontmatter — splitting and rendering the YAML block at the top of a contract file."""

import datetime

import pytest

from ato_assist import frontmatter


def test_splits_frontmatter_from_body() -> None:
    text = "---\nid: CLM-0001\n---\nThe body.\n"
    assert frontmatter.split(text) == ("id: CLM-0001\n", "The body.\n")


def test_a_file_without_frontmatter_splits_to_none_and_the_whole_text() -> None:
    assert frontmatter.split("Just prose.\n") == (None, "Just prose.\n")


def test_an_unterminated_frontmatter_block_splits_to_none() -> None:
    text = "---\nid: CLM-0001\nno closing fence\n"
    assert frontmatter.split(text) == (None, text)


def test_a_leading_blank_line_before_the_fence_is_not_frontmatter() -> None:
    text = "\n---\nid: CLM-0001\n---\n"
    assert frontmatter.split(text) == (None, text)


def test_an_empty_frontmatter_block_splits_to_an_empty_string() -> None:
    assert frontmatter.split("---\n---\nbody\n") == ("", "body\n")


def test_a_horizontal_rule_in_the_body_does_not_end_the_block_twice() -> None:
    text = "---\nid: CLM-0001\n---\nBody.\n\n---\n\nMore body.\n"
    front, body = frontmatter.split(text)
    assert front == "id: CLM-0001\n"
    assert body == "Body.\n\n---\n\nMore body.\n"


def test_parse_returns_the_mapping_and_the_body() -> None:
    data, body = frontmatter.parse("---\nid: CLM-0001\nupdated: 2026-09-02\n---\nBody.\n")
    assert data == {"id": "CLM-0001", "updated": datetime.date(2026, 9, 2)}
    assert body == "Body.\n"


def test_parse_raises_when_there_is_no_frontmatter() -> None:
    with pytest.raises(frontmatter.MissingFrontmatterError):
        frontmatter.parse("Just prose.\n")


def test_renders_a_mapping_back_to_a_document() -> None:
    text = frontmatter.render(
        {"id": "CLM-0001", "updated": datetime.date(2026, 9, 2), "state": "draft"},
        "The body.\n",
    )
    assert text == "---\nid: CLM-0001\nupdated: 2026-09-02\nstate: draft\n---\n\nThe body.\n"


def test_render_round_trips_through_parse() -> None:
    data = {
        "id": "CLM-0001",
        "source": [{"ref": "SRC-0007#anchor", "locator": "p.34"}, {"ref": "SRC-0011"}],
        "tags": ["access", "identity"],
        "classification": {"data": "OFFICIAL", "marking": "PROTECTED"},
        "count": 3,
        "open": True,
        "owner": None,
    }
    parsed, body = frontmatter.parse(frontmatter.render(data, "Body.\n"))
    assert parsed == data
    assert body == "Body.\n"


@pytest.mark.parametrize(
    "value",
    ["yes", "true", "3", "2026-09-02", "null", "", "a: b", "# hash", "on"],
)
def test_render_quotes_scalars_that_would_otherwise_change_type(value: str) -> None:
    parsed, _ = frontmatter.parse(frontmatter.render({"v": value}, ""))
    assert parsed == {"v": value}


def test_split_drops_one_blank_line_between_the_fence_and_the_body() -> None:
    assert frontmatter.split("---\nid: CLM-0001\n---\n\nBody.\n") == (
        "id: CLM-0001\n",
        "Body.\n",
    )
