"""quotation — the one definition of what "verbatim" means in this plugin.

A quote is taken from a document as the document reads. The chunk it is checked against
is what a converter produced, which carries table rendering and markdown escaping the
document never had. One function reconciles the two, and everything that compares a quote
uses it, so the answer does not depend on who is asking.
"""

import pytest

from ato_assist import quotation


def test_plain_prose_is_unchanged() -> None:
    assert quotation.flatten("The operator scans for flaws.") == "The operator scans for flaws."


def test_wrapping_is_collapsed() -> None:
    assert quotation.flatten("The operator\nscans for\nflaws.") == "The operator scans for flaws."


def test_a_sentence_split_across_grid_table_cells_reads_as_one() -> None:
    """The case that failed 30 claims: a pandoc grid table breaks every sentence."""
    chunk = (
        "| Since neither Kubernetes nor Red Hat OpenShift support    |\n"
        "| CRLs or OSCP, the advice is not to use x509 certificates. |\n"
    )
    assert quotation.flatten(chunk) == (
        "Since neither Kubernetes nor Red Hat OpenShift support CRLs or OSCP, "
        "the advice is not to use x509 certificates."
    )


def test_table_border_rules_are_dropped() -> None:
    chunk = "+------+------+\n| Role | Name |\n+======+======+\n| Owner | Ada |\n+------+------+\n"
    flat = quotation.flatten(chunk)
    assert "+" not in flat
    assert flat == "Role | Name Owner | Ada"


def test_a_column_separator_survives_because_prose_pipes_must() -> None:
    """A quote spanning two columns is not a sentence the document contains."""
    assert quotation.flatten("| Role | Name |") == "Role | Name"


def test_a_pipe_inside_prose_is_kept() -> None:
    """Only pipes doing table work are structural; one in a sentence is content."""
    assert quotation.flatten("Use a | b to pipe.") == "Use a | b to pipe."


@pytest.mark.parametrize(
    ("escaped", "plain"),
    [
        (r"each other\'s", "each other's"),
        (r"the plan\'s attachment", "the plan's attachment"),
        (r"a \[bracketed\] term", "a [bracketed] term"),
        (r"a \_underscored\_ word", "a _underscored_ word"),
        (r"100\% of nodes", "100% of nodes"),
    ],
)
def test_markdown_escapes_are_undone(escaped: str, plain: str) -> None:
    assert quotation.flatten(escaped) == plain


def test_a_backslash_before_a_letter_is_left_alone() -> None:
    """Only punctuation is escaped by a converter; `\\n` in prose is prose."""
    assert quotation.flatten(r"the path C:\node") == r"the path C:\node"


def test_contains_finds_a_quote_across_all_of_it() -> None:
    chunk = (
        "+-----------------------------------------------------------+\n"
        "| Since neither Kubernetes nor Red Hat OpenShift support     |\n"
        "| CRLs or OSCP, the advice is not to use x509 certificates\\. |\n"
        "+-----------------------------------------------------------+\n"
    )
    quote = (
        "Since neither Kubernetes nor Red Hat OpenShift support CRLs or OSCP, "
        "the advice is not to use x509 certificates."
    )
    assert quotation.contains(chunk, quote)


def test_contains_still_notices_a_missing_clause() -> None:
    """The check exists for this. Three dropped words must still fail."""
    chunk = "| The Compliance Operator scans for software flaws and improper configurations. |"
    assert not quotation.contains(
        chunk, "The Compliance Operator scans for improper configurations."
    )
