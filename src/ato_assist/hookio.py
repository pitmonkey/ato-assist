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
#
# Treat an agent's `tools:` frontmatter as documentation of intent, never as a control:
# confinement that depends on the declaration being honoured is confinement that might not
# be there. A shell is the hole in a path-based rule — a heredoc is a write the file_path
# checks never see — so a confined agent gets no shell at all.
_CONFINED_AGENTS = {"extractor", "evidence-checker"}
_CONFINED_TOOLS = {"Bash", "BashOutput", "KillShell"}
_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
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
    if str(payload.get("tool_name")) not in _WRITE_TOOLS:
        return {}  # the contract governs what is written, not what is read or run

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

    findings = validate_document(rel, text, _index(root), vocabularies=_vocabularies(root, rel))
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
        rel, text, _index(root), vocabularies=_vocabularies(root, rel)
    )
    return _nudge("PostToolUse", _render(findings)) if findings else {}


def _confinement_breach(payload: dict[str, Any]) -> Finding | None:
    """A confined agent writing anywhere but its staging area.

    Identity comes from the harness, and the honest limit of this control is that it can
    only act on what the payload says. Three cases:

    * a named confined agent — scoped to staging, and given no shell;
    * a subagent the harness names only by id — refused on the contract directories,
      because "some subagent" is not an answer to "who wrote this claim";
    * no identity at all — the main conversation, which writes the assessment.

    The third case is also what a harness that populates nothing looks like. Where that
    is true, the schema gate is the only thing standing, and it checks the shape of a
    file rather than its authorship. Do not mistake it for containment.
    """
    agent = str(payload.get("agent_type") or "").rsplit(":", 1)[-1]
    if agent not in _CONFINED_AGENTS:
        return _unidentified_writer(payload, agent)
    tool = str(payload.get("tool_name") or "")
    if tool in _CONFINED_TOOLS:
        return Finding(
            "error",
            "ATO-E002",
            tool,
            None,
            f"the {agent} agent has no shell; it reads, and writes under .ato/staging/",
            hint="write the findings to a staging file and return its path",
        )
    if tool not in _WRITE_TOOLS:
        return None  # reading is the whole point of these agents
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


def _unidentified_writer(payload: dict[str, Any], agent: str) -> Finding | None:
    """Refuse a contract write from a subagent the harness declined to name."""
    if agent or not payload.get("agent_id"):
        return None  # named, or the main conversation
    if str(payload.get("tool_name")) not in _WRITE_TOOLS:
        return None
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(file_path, str) or not file_path:
        return None
    root = find_root(file_path)
    if root is None:
        return None
    try:
        within = relative(root, file_path)
    except ValueError:
        return None
    if schema_for_path(within) is None:
        return None
    return Finding(
        "error",
        "ATO-E003",
        within,
        None,
        "this write comes from a sub-agent the hook cannot identify",
        hint="hand the findings back and let the caller write them, so the assessment "
             "has one author it can name",
    )


def _windows(parts: tuple[str, ...], size: int) -> set[tuple[str, ...]]:
    return {parts[i : i + size] for i in range(max(0, len(parts) - size + 1))}


def _vocabularies(root: Path, rel: str) -> Any:
    """The framework vocabularies, loaded independently of the index.

    Independently on purpose: `_index` is allowed to come back None, and a control's
    status must still be checked when it does. Only control writes pay for the read.
    """
    try:
        from .repo import FRAMEWORKS_DIR, Vocabularies, load_vocabularies

        if not rel.startswith("controls/"):
            return Vocabularies({}, {})
        return load_vocabularies(Path(root) / FRAMEWORKS_DIR)
    except Exception:
        return None


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
