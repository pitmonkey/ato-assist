"""hookio — turning a hook payload into a decision, in process."""

from pathlib import Path
from typing import Any

import pytest

from ato_assist import hookio

ASSESSMENT = """schema: ato-assist/assessment@1
classification:
  data: OFFICIAL
  environment: OFFICIAL
  marking: OFFICIAL
phase: intake
"""

VALID_CLAIM = """---
id: CLM-0042
title: Privileged access requires MFA
statement: All privileged access requires MFA.
source:
  - ref: SRC-0007#privileged-access
state: asserted
confidence: high
method: document-review
updated: 2026-09-02
---
Notes.
"""


SOURCE = """---
id: SRC-0007
title: System Security Plan
kind: document
received: 2026-08-14
origin: owner
classification: OFFICIAL
hash: sha256:abc
state: ingested
updated: 2026-08-14
---
## Privileged access

Text.
"""


@pytest.fixture
def assessment(tmp_path: Path) -> Path:
    (tmp_path / "claims").mkdir()
    (tmp_path / "sources" / "SRC-0007-ssp").mkdir(parents=True)
    (tmp_path / "sources" / "SRC-0007-ssp" / "index.md").write_text(SOURCE)
    (tmp_path / "assessment.yaml").write_text(ASSESSMENT)
    return tmp_path


def write_payload(path: Path, content: str) -> dict[str, Any]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(path), "content": content},
    }


def decision(result: dict[str, Any]) -> str | None:
    value = result.get("hookSpecificOutput", {}).get("permissionDecision")
    return str(value) if value is not None else None


def reason(result: dict[str, Any]) -> str:
    output = result.get("hookSpecificOutput", {})
    return str(output.get("permissionDecisionReason", "")) + str(
        output.get("additionalContext", "")
    )


def test_a_write_outside_any_assessment_is_ignored(tmp_path: Path) -> None:
    assert hookio.handle_pre(write_payload(tmp_path / "notes.md", "hi")) == {}


def test_a_payload_with_no_file_path_is_ignored() -> None:
    assert hookio.handle_pre({"tool_name": "Bash", "tool_input": {"command": "ls"}}) == {}


def test_the_plugins_own_fixtures_do_not_trip_the_hook(assessment: Path) -> None:
    path = assessment / "tests" / "fixtures" / "repos" / "dirty" / "claims" / "CLM-0001-a.md"
    assert hookio.handle_pre(write_payload(path, "broken")) == {}


def test_a_write_outside_a_contract_directory_is_ignored(assessment: Path) -> None:
    assert hookio.handle_pre(write_payload(assessment / "notes.md", "anything")) == {}


def test_a_conformant_claim_is_allowed(assessment: Path) -> None:
    payload = write_payload(assessment / "claims" / "CLM-0042-mfa.md", VALID_CLAIM)
    assert hookio.handle_pre(payload) == {}


def test_an_unsourced_claim_is_denied_with_its_code(assessment: Path) -> None:
    content = VALID_CLAIM.replace("source:\n  - ref: SRC-0007#privileged-access\n", "")
    payload = write_payload(assessment / "claims" / "CLM-0042-mfa.md", content)
    result = hookio.handle_pre(payload)
    assert decision(result) == "deny"
    assert "ATO-E110" in reason(result)


def test_an_incomplete_classification_denies_the_write(tmp_path: Path) -> None:
    (tmp_path / "claims").mkdir()
    (tmp_path / "assessment.yaml").write_text("classification:\n  data: OFFICIAL\n")
    payload = write_payload(tmp_path / "claims" / "CLM-0042-mfa.md", VALID_CLAIM)
    result = hookio.handle_pre(payload)
    assert decision(result) == "deny"
    assert "ATO-E001" in reason(result)


def test_the_deny_reason_is_capped(assessment: Path) -> None:
    content = "---\nid: CLM-0042\n" + "".join(f"junk{n}: x\n" for n in range(40)) + "---\n"
    payload = write_payload(assessment / "claims" / "CLM-0042-mfa.md", content)
    result = hookio.handle_pre(payload)
    assert decision(result) == "deny"
    assert len(reason(result)) <= 1500


def test_an_edit_is_validated_against_the_reconstructed_file(assessment: Path) -> None:
    path = assessment / "claims" / "CLM-0042-mfa.md"
    path.write_text(VALID_CLAIM)
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(path),
            "old_string": "  - ref: SRC-0007#privileged-access\n",
            "new_string": "",
        },
    }
    result = hookio.handle_pre(payload)
    assert decision(result) == "deny"
    assert "ATO-E110" in reason(result)


def test_an_edit_that_keeps_the_file_valid_is_allowed(assessment: Path) -> None:
    path = assessment / "claims" / "CLM-0042-mfa.md"
    path.write_text(VALID_CLAIM)
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(path),
            "old_string": "state: asserted",
            "new_string": "state: corroborated",
        },
    }
    assert hookio.handle_pre(payload) == {}


def test_an_ambiguous_edit_nudges_rather_than_denying(assessment: Path) -> None:
    path = assessment / "claims" / "CLM-0042-mfa.md"
    path.write_text(VALID_CLAIM)
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(path), "old_string": "e", "new_string": "E"},
    }
    result = hookio.handle_pre(payload)
    assert decision(result) is None
    assert "after it is written" in reason(result)


def test_a_multiedit_applies_every_edit_in_order(assessment: Path) -> None:
    path = assessment / "claims" / "CLM-0042-mfa.md"
    path.write_text(VALID_CLAIM)
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(path),
            "edits": [
                {"old_string": "state: asserted", "new_string": "state: bogus"},
                {"old_string": "confidence: high", "new_string": "confidence: low"},
            ],
        },
    }
    result = hookio.handle_pre(payload)
    assert decision(result) == "deny"
    assert "ATO-E103" in reason(result)


def test_post_never_denies_even_for_a_broken_file(assessment: Path) -> None:
    path = assessment / "claims" / "CLM-0042-mfa.md"
    path.write_text("no frontmatter here")
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(path)},
    }
    result = hookio.handle_post(payload)
    assert decision(result) is None
    assert "ATO-E101" in reason(result)


def test_post_is_silent_about_a_conformant_file(assessment: Path) -> None:
    path = assessment / "claims" / "CLM-0042-mfa.md"
    path.write_text(VALID_CLAIM)
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(path)}}
    assert hookio.handle_post(payload) == {}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"tool_input": None},
        {"tool_name": "Write", "tool_input": {"file_path": ""}},
        {"tool_name": "Write", "tool_input": {"file_path": "/nonexistent/x/y.md"}},
    ],
)
def test_malformed_payloads_produce_no_decision(payload: dict[str, Any]) -> None:
    assert hookio.handle_pre(payload) == {}


def test_a_claim_citing_a_source_that_does_not_exist_yet_nudges(assessment: Path) -> None:
    """The source may be written later in the same turn; denying that would be hostile."""
    content = VALID_CLAIM.replace("SRC-0007", "SRC-0099")
    payload = write_payload(assessment / "claims" / "CLM-0042-mfa.md", content)
    result = hookio.handle_pre(payload)
    assert decision(result) is None
    assert "ATO-E112" in reason(result)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("state: asserted", "state: corroborated"),
        ("  - ref: SRC-0007#privileged-access\n", ""),
        ("confidence: high", "confidence: bogus"),
    ],
    ids=["valid-edit", "removes-source", "bad-enum"],
)
def test_an_edit_is_judged_exactly_as_the_written_file_would_be(
    assessment: Path, old: str, new: str
) -> None:
    """Reconstruction must agree with the file the edit would produce, or the hook lies."""
    from ato_assist import validate

    path = assessment / "claims" / "CLM-0042-mfa.md"
    path.write_text(VALID_CLAIM)
    expected = VALID_CLAIM.replace(old, new)

    reconstructed, mode = hookio.candidate_text(
        "Edit", {"file_path": str(path), "old_string": old, "new_string": new}
    )
    assert mode == "exact"
    assert reconstructed == expected

    written, _ = hookio.candidate_text("Write", {"content": expected})
    relative = "claims/CLM-0042-mfa.md"
    assert validate.validate_document(relative, reconstructed or "") == validate.validate_document(
        relative, written or ""
    )
