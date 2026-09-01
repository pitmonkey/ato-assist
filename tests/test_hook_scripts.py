"""The hook process contract: whatever happens, exit 0 and never disrupt the session."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import HOOK_BOOTSTRAP, PLUGIN_ROOT, hook_json, run_hook

SCRIPTS = ["pretooluse_guard.py", "posttooluse_guard.py", "sessionstart_brief.py"]

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
"""


@pytest.fixture
def assessment(tmp_path: Path) -> Path:
    (tmp_path / "claims").mkdir()
    (tmp_path / "assessment.yaml").write_text(
        "classification:\n  data: OFFICIAL\n  environment: OFFICIAL\n  marking: OFFICIAL\n"
        "phase: intake\n"
    )
    return tmp_path


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize(
    "stdin",
    [
        "",
        "not json at all",
        "{",
        "[]",
        '{"tool_input": null}',
        '{"tool_name": "Write", "tool_input": {"file_path": "/nope/x.md", "content": "x"}}',
    ],
    ids=["empty", "garbage", "truncated", "array", "null-input", "outside-assessment"],
)
def test_a_hook_always_exits_zero(script: str, stdin: str) -> None:
    code, stdout, _ = run_hook(script, stdin)
    assert code == 0
    assert hook_json(stdout).get("hookSpecificOutput", {}).get("permissionDecision") is None


def test_a_hook_survives_non_utf8_input() -> None:
    process = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "hooks" / "pretooluse_guard.py")],
        input=b"\xff\xfe not utf-8",
        capture_output=True,
    )
    assert process.returncode == 0


def test_a_hook_survives_a_very_large_payload(assessment: Path) -> None:
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(assessment / "claims" / "CLM-0042-mfa.md"),
            "content": VALID_CLAIM + "x" * 5_000_000,
        },
    }
    code, _, _ = run_hook("pretooluse_guard.py", json.dumps(payload))
    assert code == 0


def test_the_pretooluse_hook_denies_an_unsourced_claim(assessment: Path) -> None:
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(assessment / "claims" / "CLM-0042-mfa.md"),
            "content": VALID_CLAIM.replace("  - ref: SRC-0007#privileged-access\n", ""),
        },
    }
    code, stdout, _ = run_hook("pretooluse_guard.py", json.dumps(payload))
    assert code == 0
    output = hook_json(stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert "ATO-E110" in output["permissionDecisionReason"]


def test_the_pretooluse_hook_is_silent_for_a_conformant_claim(assessment: Path) -> None:
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(assessment / "claims" / "CLM-0042-mfa.md"),
            "content": VALID_CLAIM,
        },
    }
    code, stdout, _ = run_hook("pretooluse_guard.py", json.dumps(payload))
    assert (code, stdout.strip()) == (0, "")


def test_a_hook_runs_without_the_plugin_root_variable(assessment: Path) -> None:
    """A hook must find its own package even if the environment variable is absent."""
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(assessment / "claims" / "CLM-0042-mfa.md"),
            "content": VALID_CLAIM.replace("  - ref: SRC-0007#privileged-access\n", ""),
        },
    }
    process = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "hooks" / "pretooluse_guard.py")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(assessment)},
    )
    assert process.returncode == 0
    assert "ATO-E110" in process.stdout


def test_hook_modules_never_reach_for_a_third_party_package_or_the_cli() -> None:
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            HOOK_BOOTSTRAP + "; import json,sys; print(json.dumps(sorted(sys.modules)))",
        ],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    loaded = set(json.loads(process.stdout))
    forbidden = {
        "yaml",
        "ato_assist.cli",
        "ato_assist.status",
        "ato_assist.checks",
        "ato_assist.ingest",
        "ato_assist.export",
        "ato_assist.scaffold",
    }
    assert not loaded & forbidden
