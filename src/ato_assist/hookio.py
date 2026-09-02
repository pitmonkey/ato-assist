"""Turning a hook payload into a decision.

The hook entry points under ``hooks/`` are deliberately thin — read stdin, call one of
these, print the result, exit 0 — so that the interesting behaviour is testable in
process rather than only through a subprocess.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .repo import find_root, load_assessment, relative
from .validate import Finding, classification_gate, schema_for_path, validate_document

__all__ = ["candidate_text", "handle_post", "handle_pre"]

# The plugin's own fixture repositories are valid assessments by construction; without
# this guard, developing the plugin would trip its own hooks.
_DEV_FIXTURES = "/tests/fixtures/"
_MAX_FINDINGS = 5
_MAX_REASON = 1500

# The extractor reads large documents and returns structured findings. Its output routinely
# exceeds what a subagent reply can carry, so it writes to a staging file and returns the
# path — but it must never touch the assessment itself. That confinement is enforced here
# rather than by withholding the Write tool, because a rule the hook enforces holds however
# the agent is configured, and every other rule in this plugin works the same way.
_CONFINED_AGENTS = {"extractor", "evidence-checker"}
_STAGING = (".ato", "staging")


def candidate_text(tool_name: str, tool_input: dict[str, Any]) -> tuple[str | None, str]:
    """The content a tool call is about to produce, and how certain we are of it.

    ``("...", "exact")`` when the post-write text is known: a Write carries it outright,
    and an Edit is a literal string replacement that can be replayed against the file on
    disk. ``(None, "none")`` when it is not — an unreadable file, or a replacement whose
    match count is not one, which Claude Code would reject anyway.
    """
    if tool_name == "Write":
        content = tool_input.get("content")
        return (content, "exact") if isinstance(content, str) else (None, "none")

    if tool_name not in ("Edit", "MultiEdit"):
        return None, "none"

    try:
        text = Path(str(tool_input.get("file_path"))).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None, "none"

    edits = tool_input.get("edits") or [tool_input]
    for edit in edits:
        old = edit.get("old_string", "")
        new = edit.get("new_string", "")
        if edit.get("replace_all"):
            text = text.replace(old, new)
        elif text.count(old) == 1:
            text = text.replace(old, new, 1)
        else:
            return None, "none"
    return text, "exact"


def handle_pre(payload: dict[str, Any]) -> dict[str, Any]:
    """Decide a PreToolUse call: deny, nudge, or say nothing."""
    confined = _confinement_breach(payload)
    if confined:
        return _deny([confined], "PreToolUse")

    located = _locate(payload)
    if located is None:
        return {}
    root, rel = located

    gate = classification_gate(rel, load_assessment(root))
    if gate:
        return _deny(gate, "PreToolUse")

    tool_input = payload.get("tool_input") or {}
    text, mode = candidate_text(str(payload.get("tool_name")), tool_input)
    if mode != "exact" or text is None:
        return _nudge(
            "PreToolUse",
            f"ATO: could not reconstruct the result of this edit to {rel}, so it will be "
            "checked against the contract after it is written.",
        )

    findings = validate_document(rel, text, _index(root))
    errors = [f for f in findings if f.level == "error"]
    if errors:
        return _deny(errors, "PreToolUse")
    warnings = [f for f in findings if f.level == "warn"]
    return _nudge("PreToolUse", _render(warnings)) if warnings else {}


def handle_post(payload: dict[str, Any]) -> dict[str, Any]:
    """Report on a file that has already been written. This can only ever nudge."""
    located = _locate(payload)
    if located is None:
        return {}
    root, rel = located
    try:
        text = (Path(root) / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    findings = classification_gate(rel, load_assessment(root)) + validate_document(
        rel, text, _index(root)
    )
    return _nudge("PostToolUse", _render(findings)) if findings else {}


def _confinement_breach(payload: dict[str, Any]) -> Finding | None:
    """A confined agent writing anywhere but its staging area."""
    agent = str(payload.get("agent_type") or "").rsplit(":", 1)[-1]
    if agent not in _CONFINED_AGENTS:
        return None
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return None
    if _STAGING in _windows(Path(file_path).parts, len(_STAGING)):
        return None
    return Finding(
        "error",
        "ATO-E002",
        file_path,
        None,
        f"the {agent} agent may only write under .ato/staging/",
        hint="return the staging path and the counts; the caller writes the assessment",
    )


def _windows(parts: tuple[str, ...], size: int) -> set[tuple[str, ...]]:
    return {parts[i : i + size] for i in range(max(0, len(parts) - size + 1))}


def _index(root: Path) -> Any:
    """The referential layer, or None if building it fails. A hook never dies for this."""
    try:
        from .repo import RepoIndex

        return RepoIndex(root)
    except Exception:
        return None


def _locate(payload: dict[str, Any]) -> tuple[Path, str] | None:
    """The assessment root and repo-relative path this payload concerns, if any.

    Everything before the validator lives here, and it is all cheap: the overwhelming
    majority of tool calls have nothing to do with an assessment and must not pay for
    the schema machinery.
    """
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return None
    if _DEV_FIXTURES in file_path:
        return None
    root = find_root(file_path)
    if root is None:
        return None
    try:
        rel = relative(root, file_path)
    except ValueError:
        return None
    return (root, rel) if schema_for_path(rel) is not None else None


def _render(findings: list[Finding]) -> str:
    lines: list[str] = []
    for finding in findings[:_MAX_FINDINGS]:
        where = f" ({finding.field})" if finding.field else ""
        line = f"{finding.code} {finding.path}{where}: {finding.message}"
        if finding.hint:
            line += f"\n  {finding.hint}"
        lines.append(line)
    if len(findings) > _MAX_FINDINGS:
        lines.append(f"... and {len(findings) - _MAX_FINDINGS} more")
    return "\n".join(lines)[:_MAX_REASON]


def _deny(findings: list[Finding], event: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "permissionDecision": "deny",
            "permissionDecisionReason": _render(findings),
        },
        "systemMessage": f"ATO: write rejected — {findings[0].code}",
    }


def _nudge(event: str, message: str) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}
