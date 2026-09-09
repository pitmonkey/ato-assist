"""L1 validation: everything decidable from a single document's own text."""

from pathlib import Path

import pytest

from ato_assist import validate
from tests_support import ism_vocabularies

CONTROL_PATH = "controls/ism/ISM-0421.md"


def check(text: str, path: str = CONTROL_PATH) -> list[validate.Finding]:
    """Validate a control against the shipped ISM vocabulary."""
    return validate.validate_document(path, text, vocabularies=ism_vocabularies())

VALID_CLAIM = """---
id: CLM-0042
title: Privileged access requires MFA
statement: All privileged access to the management plane requires phishing-resistant MFA.
source:
  - ref: SRC-0007#privileged-access
    quote: "All privileged access requires phishing-resistant MFA."
state: asserted
confidence: high
method: document-review
updated: 2026-09-02
---
Assessor notes.
"""


def codes(findings: list[validate.Finding]) -> list[str]:
    return [finding.code for finding in findings]


def test_a_conformant_claim_produces_no_findings() -> None:
    assert validate.validate_document("claims/CLM-0042-mfa.md", VALID_CLAIM) == []


def test_a_file_outside_a_contract_directory_is_not_validated() -> None:
    assert validate.validate_document("notes/system-context.md", "anything at all") == []


def test_missing_frontmatter_is_e101() -> None:
    findings = validate.validate_document("claims/CLM-0042-mfa.md", "Just prose.\n")
    assert codes(findings) == ["ATO-E101"]


def test_unparseable_frontmatter_is_e101_and_names_the_line() -> None:
    text = "---\nid: CLM-0042\n\tbad: tab\n---\n"
    findings = validate.validate_document("claims/CLM-0042-mfa.md", text)
    assert codes(findings) == ["ATO-E101"]
    assert "line 3" in findings[0].message


def test_a_missing_required_field_is_e102() -> None:
    text = VALID_CLAIM.replace("state: asserted\n", "")
    findings = validate.validate_document("claims/CLM-0042-mfa.md", text)
    assert codes(findings) == ["ATO-E102"]
    assert findings[0].field == "state"


def test_a_value_outside_a_closed_enum_is_e103() -> None:
    text = VALID_CLAIM.replace("state: asserted", "state: pending")
    findings = validate.validate_document("claims/CLM-0042-mfa.md", text)
    assert codes(findings) == ["ATO-E103"]
    assert "pending" in findings[0].message


def test_an_unknown_field_is_e104() -> None:
    text = VALID_CLAIM.replace("state: asserted", "state: asserted\nseverity: high")
    findings = validate.validate_document("claims/CLM-0042-mfa.md", text)
    assert codes(findings) == ["ATO-E104"]
    assert findings[0].field == "severity"


def test_an_empty_source_list_is_e110() -> None:
    text = VALID_CLAIM.replace(
        'source:\n  - ref: SRC-0007#privileged-access\n    quote: "All privileged'
        " access requires phishing-resistant MFA.\"\n",
        "source: []\n",
    )
    findings = validate.validate_document("claims/CLM-0042-mfa.md", text)
    assert codes(findings) == ["ATO-E110"]


def test_a_malformed_ref_is_e111() -> None:
    text = VALID_CLAIM.replace("SRC-0007#privileged-access", "../sources/ssp.md")
    findings = validate.validate_document("claims/CLM-0042-mfa.md", text)
    assert codes(findings) == ["ATO-E111"]


def test_a_ref_to_a_claim_from_a_claim_is_e111() -> None:
    text = VALID_CLAIM.replace("SRC-0007#privileged-access", "CLM-0001")
    findings = validate.validate_document("claims/CLM-0042-mfa.md", text)
    assert codes(findings) == ["ATO-E111"]


def test_an_id_disagreeing_with_the_filename_is_e120() -> None:
    findings = validate.validate_document("claims/CLM-0001-mfa.md", VALID_CLAIM)
    assert codes(findings) == ["ATO-E120"]


def test_ad_hoc_method_with_high_confidence_is_e140() -> None:
    text = VALID_CLAIM.replace("method: document-review", "method: ad-hoc")
    findings = validate.validate_document("claims/CLM-0042-mfa.md", text)
    assert codes(findings) == ["ATO-E140"]


def test_ad_hoc_method_with_medium_confidence_is_allowed() -> None:
    text = VALID_CLAIM.replace("method: document-review", "method: ad-hoc").replace(
        "confidence: high", "confidence: medium"
    )
    assert validate.validate_document("claims/CLM-0042-mfa.md", text) == []


VALID_CONTROL = """---
id: ISM-0421
framework: ism
title: Privileged access is restricted
status: effective
claims: [CLM-0042]
evidence: [EVD-0003]
confidence: high
method: document-review
updated: 2026-09-02
---
Rationale.
"""

CITATIONS = "claims: [CLM-0042]\nevidence: [EVD-0003]\n"


def test_a_conformant_control_produces_no_findings() -> None:
    assert check(VALID_CONTROL) == []


def test_an_assessed_control_citing_neither_claims_nor_evidence_is_e110() -> None:
    assert codes(check(VALID_CONTROL.replace(CITATIONS, ""))) == ["ATO-E110"]


def test_an_unassessed_control_may_cite_nothing() -> None:
    text = VALID_CONTROL.replace(CITATIONS, "").replace(
        "status: effective", "status: not-assessed"
    )
    assert check(text) == []


def test_a_not_applicable_control_citing_only_evidence_is_e110() -> None:
    text = VALID_CONTROL.replace("claims: [CLM-0042]\n", "").replace(
        "status: effective", "status: not-applicable"
    )
    findings = check(text)
    assert codes(findings) == ["ATO-E110"]
    assert "claim" in findings[0].message


def test_a_control_whose_framework_disagrees_with_its_directory_is_e121() -> None:
    assert codes(check(VALID_CONTROL.replace("framework: ism", "framework: e8"))) == [
        "ATO-E121"
    ]


# --- the vocabulary is the framework's, and it has changed ----------------------------


def test_an_alternate_control_citing_a_claim_is_conformant() -> None:
    """The rating the old vocabulary could not express at all, which is why #15 exists."""
    assert check(VALID_CONTROL.replace("status: effective", "status: alternate-control")) == []


def test_an_alternate_control_citing_only_evidence_is_e110() -> None:
    """Accepting a compensating control is an argument, so something must argue it."""
    text = VALID_CONTROL.replace("claims: [CLM-0042]\n", "").replace(
        "status: effective", "status: alternate-control"
    )
    findings = check(text)
    assert codes(findings) == ["ATO-E110"]
    assert "claim" in findings[0].message


def test_a_status_from_the_retired_vocabulary_is_e105_naming_its_replacement() -> None:
    """The half of the corpus the old vocabulary accepts and the new one rejects."""
    findings = check(VALID_CONTROL.replace("status: effective", "status: satisfied"))
    assert codes(findings) == ["ATO-E105"]
    assert "'effective'" in findings[0].message


def test_inherited_migrates_to_effective_and_says_the_claim_is_now_the_record() -> None:
    findings = check(VALID_CONTROL.replace("status: effective", "status: inherited"))
    assert codes(findings) == ["ATO-E105"]
    assert "'effective'" in findings[0].message
    assert "claim" in findings[0].hint


def test_partially_satisfied_migrates_to_ineffective_and_asks_for_a_re_check() -> None:
    text = VALID_CONTROL.replace("status: effective", "status: partially-satisfied")
    findings = check(text)
    assert codes(findings) == ["ATO-E105"]
    assert "'ineffective'" in findings[0].message
    assert "re-check" in findings[0].hint


def test_a_status_no_vocabulary_has_ever_carried_is_still_e103() -> None:
    findings = check(VALID_CONTROL.replace("status: effective", "status: banana"))
    assert codes(findings) == ["ATO-E103"]
    assert "alternate-control" in findings[0].message


def test_the_enum_message_names_the_framework_whose_vocabulary_it_is() -> None:
    findings = check(VALID_CONTROL.replace("status: effective", "status: banana"))
    assert "ism" in findings[0].hint


E8 = """schema: ato-assist/framework@1
id: e8
status:
  values: [not-assessed, maturity-1, maturity-2]
  unassessed: not-assessed
  uncited: [not-assessed]
"""


def test_a_status_valid_in_another_framework_is_e103_in_this_one(tmp_path: Path) -> None:
    """Each framework's vocabulary judges only its own directory."""
    from ato_assist import repo

    (tmp_path / "e8.yaml").write_text(E8)
    vocabularies = repo.load_vocabularies(tmp_path)
    text = VALID_CONTROL.replace("framework: ism", "framework: e8").replace(
        "id: ISM-0421", "id: ML1-01"
    )
    findings = validate.validate_document(
        "controls/e8/ML1-01.md", text, vocabularies=vocabularies
    )
    assert codes(findings) == ["ATO-E103"]
    assert "maturity-1" in findings[0].message
    assert "alternate-control" not in findings[0].message


def test_a_control_whose_framework_has_no_vocabulary_warns_rather_than_denying() -> None:
    """A config fault the write cannot fix must never block the write."""
    from ato_assist import repo

    findings = validate.validate_document(
        "controls/nope/X-0001.md",
        VALID_CONTROL.replace("framework: ism", "framework: nope").replace(
            "id: ISM-0421", "id: X-0001"
        ),
        vocabularies=repo.Vocabularies({}, {}),
    )
    assert codes(findings) == ["ATO-E004"]
    assert findings[0].level == "warn"
    assert "frameworks/nope.yaml" in findings[0].hint


def test_without_a_vocabulary_the_status_is_not_checked_at_all() -> None:
    """The layer that needs no framework config, mirroring `repo=None`."""
    assert validate.validate_document(CONTROL_PATH, VALID_CONTROL) == []
    assert validate.validate_document(
        CONTROL_PATH, VALID_CONTROL.replace("status: effective", "status: banana")
    ) == []


VALID_RISK = """---
id: RSK-0001
title: Unmonitored privileged access
statement: Privileged access is unmonitored, so misuse would go undetected.
threat: A malicious insider
vulnerability: No privileged session logging
consequence: Undetected data exfiltration
likelihood: possible
impact: major
refs: [CLM-0042, ISM-0421]
state: accepted
owner: System owner
disposition: Accepted pending Q4 remediation
updated: 2026-09-02
---
"""


def test_a_conformant_risk_produces_no_findings() -> None:
    assert validate.validate_document("risks/RSK-0001-privileged.md", VALID_RISK) == []


def test_an_accepted_risk_without_a_disposition_is_e102() -> None:
    text = VALID_RISK.replace("disposition: Accepted pending Q4 remediation\n", "")
    findings = validate.validate_document("risks/RSK-0001-privileged.md", text)
    assert codes(findings) == ["ATO-E102"]
    assert findings[0].field == "disposition"


def test_a_draft_risk_needs_no_owner() -> None:
    text = (
        VALID_RISK.replace("state: accepted", "state: draft")
        .replace("owner: System owner\n", "")
        .replace("disposition: Accepted pending Q4 remediation\n", "")
    )
    assert validate.validate_document("risks/RSK-0001-privileged.md", text) == []


VALID_RFI = """---
id: RFI-0003
title: Conditional access policy export
question: Please provide the current conditional access policy export.
asked_of: System owner
asked_on: 2026-08-19
state: answered
answered_on: 2026-08-30
answer_source:
  - ref: SRC-0011
updated: 2026-08-30
---
"""


def test_a_conformant_rfi_produces_no_findings() -> None:
    assert validate.validate_document("rfi/RFI-0003-ca-export.md", VALID_RFI) == []


def test_an_answered_rfi_without_an_answer_source_is_e102() -> None:
    text = VALID_RFI.replace("answer_source:\n  - ref: SRC-0011\n", "")
    findings = validate.validate_document("rfi/RFI-0003-ca-export.md", text)
    assert codes(findings) == ["ATO-E102"]
    assert findings[0].field == "answer_source"


VALID_EVIDENCE = """---
id: EVD-0003
title: Conditional access policy export
bears_on: [CLM-0042]
direction: supports
artifact:
  - inbox/ca-policies-2026-08.json
method: config-review
collected: 2026-08-30
collected_by: Customer
state: accepted
updated: 2026-08-30
---
Reasoning.
"""


def test_a_conformant_evidence_entry_produces_no_findings() -> None:
    assert validate.validate_document("evidence/EVD-0003-ca.md", VALID_EVIDENCE) == []


def test_evidence_bearing_on_nothing_is_e110() -> None:
    text = VALID_EVIDENCE.replace("bears_on: [CLM-0042]", "bears_on: []")
    findings = validate.validate_document("evidence/EVD-0003-ca.md", text)
    assert codes(findings) == ["ATO-E110"]


def test_evidence_bearing_on_a_non_claim_is_e111() -> None:
    text = VALID_EVIDENCE.replace("bears_on: [CLM-0042]", "bears_on: [SRC-0007]")
    findings = validate.validate_document("evidence/EVD-0003-ca.md", text)
    assert codes(findings) == ["ATO-E111"]


VALID_SOURCE = """---
id: SRC-0007
title: System Security Plan v2.4
kind: document
received: 2026-08-14
origin: System owner
classification: PROTECTED
hash: sha256:0f9a
state: ingested
updated: 2026-08-14
---
"""


def test_a_conformant_source_index_produces_no_findings() -> None:
    assert validate.validate_document("sources/SRC-0007-ssp-v2-4/index.md", VALID_SOURCE) == []


def test_a_source_id_disagreeing_with_its_directory_is_e120() -> None:
    findings = validate.validate_document("sources/SRC-0001-ssp/index.md", VALID_SOURCE)
    assert codes(findings) == ["ATO-E120"]


def test_a_chunk_file_inside_a_source_directory_is_not_validated() -> None:
    assert validate.validate_document("sources/SRC-0007-ssp/03-access.md", "# Access\n") == []


@pytest.mark.parametrize(
    "path",
    ["claims/notes.md", "claims/CLM-42-short.md", "risks/RSK-0001.md"],
)
def test_a_filename_outside_the_naming_convention_is_e122(path: str) -> None:
    findings = validate.validate_document(path, VALID_CLAIM)
    assert "ATO-E122" in codes(findings)


def test_a_readme_explaining_a_contract_directory_is_not_an_item() -> None:
    assert validate.validate_document("claims/README.md", "# `claims/`\n\nWhat goes here.\n") == []


def test_a_draft_risk_may_wait_for_the_assessors_rating() -> None:
    """The rating is the assessor's judgement, so a draft must be fileable without one."""
    text = (
        VALID_RISK.replace("likelihood: possible\n", "")
        .replace("impact: major\n", "")
        .replace("state: accepted", "state: draft")
        .replace("owner: System owner\n", "")
        .replace("disposition: Accepted pending Q4 remediation\n", "")
    )
    assert validate.validate_document("risks/RSK-0001-privileged.md", text) == []


def test_a_risk_leaving_draft_needs_its_rating() -> None:
    text = VALID_RISK.replace("likelihood: possible\n", "").replace(
        "state: accepted", "state: open"
    ).replace("disposition: Accepted pending Q4 remediation\n", "")
    findings = validate.validate_document("risks/RSK-0001-privileged.md", text)
    assert [f.code for f in findings] == ["ATO-E102"]
    assert findings[0].field == "likelihood"
