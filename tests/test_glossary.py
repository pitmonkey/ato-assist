"""glossary — finding terms nobody has defined, without stopping to ask about each one."""

from __future__ import annotations

from pathlib import Path

from ato_assist import glossary

BASELINE = "## ATO — Authority to Operate\n\nText.\n\n## SSP — System Security Plan\n\nText.\n"


def test_reads_defined_terms_from_a_glossary_heading() -> None:
    assert glossary.defined_terms(BASELINE) == {"ATO", "SSP"}


def test_a_heading_without_an_expansion_still_defines_the_term() -> None:
    assert glossary.defined_terms("## Essential Eight\n\n## MFA\n") == {"MFA", "Essential Eight"}


def test_finds_acronyms_in_prose() -> None:
    found = glossary.scan("The SIEM forwards to the SOC. The SIEM is managed.")
    assert set(found) == {"SIEM", "SOC"}


def test_counts_each_acronym() -> None:
    found = glossary.scan("The SIEM forwards to the SOC. The SIEM is managed.")
    assert found["SIEM"].sightings == 2


def test_keeps_a_sample_sentence_so_the_assessor_can_see_the_context() -> None:
    found = glossary.scan("Nothing here. The SIEM forwards to the SOC. More text.")
    assert found["SIEM"].sample == "The SIEM forwards to the SOC."


def test_matches_acronyms_carrying_digits() -> None:
    assert "ISM2" in glossary.scan("Refer to ISM2 for detail.")


def test_ignores_words_that_are_too_short_or_too_long() -> None:
    found = glossary.scan("A GOVERNMENTAL body and an OS and a VPC.")
    assert set(found) == {"VPC"}


def test_ignores_a_fully_capitalised_sentence_fragment() -> None:
    # Headings and emphasis produce runs of capitals that are words, not acronyms.
    found = glossary.scan("SYSTEM SECURITY PLAN\n\nThe VPC is isolated.")
    assert set(found) == {"VPC"}


def test_unresolved_excludes_terms_already_defined_anywhere() -> None:
    unresolved = glossary.unresolved(
        "The SIEM and the SSP and the ATO.", defined=glossary.defined_terms(BASELINE)
    )
    assert set(unresolved) == {"SIEM"}


def test_rendering_the_queue_keeps_existing_rows_and_merges_counts() -> None:
    existing = (
        "# Unresolved terms\n\n"
        "| Term | Count | First seen | Sample |\n|------|-------|-----------|--------|\n"
        "| SIEM | 2 | SRC-0001 | The SIEM forwards. |\n"
    )
    found = glossary.scan("The SIEM again. And a VPC.")
    table = glossary.merge_queue(existing, found, source_id="SRC-0002")
    assert "| SIEM | 3 | SRC-0001 |" in table
    assert "| VPC | 1 | SRC-0002 |" in table


def test_a_pipe_in_a_sample_cannot_break_the_table() -> None:
    found = glossary.scan("The VPC | is odd.")
    row = glossary.merge_queue("", found, source_id="SRC-0001").splitlines()[-1]
    assert row.count("|") - row.count("\\|") == 5


def test_the_queue_is_written_next_to_the_glossary(tmp_path: Path) -> None:
    (tmp_path / "glossary").mkdir()
    queue = tmp_path / "glossary" / "unresolved.md"
    queue.write_text(
        "# Unresolved terms\n\n| Term | Count | First seen | Sample |\n|--|--|--|--|\n"
    )
    glossary.record(tmp_path, "The VPC is isolated.", source_id="SRC-0001", defined=set())
    assert "| VPC | 1 | SRC-0001 |" in queue.read_text()
