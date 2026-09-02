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


def test_a_separator_with_an_empty_cell_to_its_left_is_a_cell_wall() -> None:
    """Pandoc repeats every column separator on a wrapped cell's continuation lines.

    A pipe with nothing but whitespace between it and the start of the line cannot be
    punctuation: there is no sentence to its left for it to punctuate.
    """
    chunk = (
        "|                | nodes. The API servers do not support retaining audit logs  |\n"
        "|                | for at least a defined number of days.                      |\n"
    )
    assert quotation.flatten(chunk) == (
        "nodes. The API servers do not support retaining audit logs for at least a "
        "defined number of days."
    )


def test_a_control_narrative_beside_its_label_reads_as_one_sentence() -> None:
    """The normal shape here: a label in column one, prose wrapped in column two."""
    chunk = (
        "| **Part a**     | The organisation offloads audit logs from the cluster to a   |\n"
        "|                | central store within one day.                               |\n"
    )
    assert quotation.contains(
        chunk,
        "The organisation offloads audit logs from the cluster to a central store within one day.",
    )


def test_several_empty_leading_cells_are_all_walls() -> None:
    assert quotation.flatten("|   |   | the text |") == "the text"


def test_a_pipe_after_real_content_is_still_left_alone() -> None:
    """The ambiguous case is unchanged: this could be a column break or prose."""
    assert quotation.flatten("| Role | Name |") == "Role | Name"


def test_prose_beginning_with_a_pipe_is_not_eaten() -> None:
    assert quotation.flatten("Use a | b to pipe.") == "Use a | b to pipe."


def test_a_quote_spanning_two_columns_of_one_row_still_does_not_match() -> None:
    """Not a sentence the document contains. Such a claim cites both cells instead."""
    chunk = "| Not applicable | The control is inherited from the platform. |"
    assert not quotation.contains(
        chunk, "Not applicable The control is inherited from the platform."
    )


def test_a_simple_tables_header_rule_is_dropped() -> None:
    """A pandoc simple table underlines its header with runs of hyphens, not a border."""
    chunk = (
        "**Implementation Status**   **Count**\n"
        "--------------------------- ----------\n"
        "Not applicable              253\n"
        "Implemented                 61\n"
    )
    assert quotation.flatten(chunk) == (
        "**Implementation Status** **Count** Not applicable 253 Implemented 61"
    )


@pytest.mark.parametrize(
    "rule",
    ["--------- ------", "=====  ====", "   ----------   ", "--- --- ---"],
)
def test_rules_of_every_shape_are_dropped(rule: str) -> None:
    assert quotation.flatten(f"Heading\n{rule}\nBody text.") == "Heading Body text."


@pytest.mark.parametrize("prose", ["- a bullet point", "a - b", "the range 5 - 10"])
def test_prose_containing_hyphens_survives(prose: str) -> None:
    assert prose.strip("- ") in quotation.flatten(prose)
