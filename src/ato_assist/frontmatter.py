"""Splitting, parsing and rendering the YAML frontmatter block of a contract file.

Contract files are markdown with a leading ``---`` fenced YAML block. Frontmatter holds
the facts, which must be sourced and are validated; the body is prose, which is not.
"""

from __future__ import annotations

import datetime
import re
from typing import Any

from .miniyaml import loads

__all__ = ["MissingFrontmatterError", "parse", "render", "split"]

_FENCE = "---"
# A bare scalar that YAML would read as something other than a plain string.
_TYPED_LOOKING = re.compile(
    r"^(|~|[Nn]ull|NULL|[Tt]rue|TRUE|[Ff]alse|FALSE|[Yy]es|[Nn]o|[Oo]n|[Oo]ff|[YyNn]"
    r"|[+-]?\d+|[+-]?(\d+\.\d*|\.\d+)([eE][+-]?\d+)?|\d{4}-\d{2}-\d{2}.*)$"
)


class MissingFrontmatterError(ValueError):
    """The file has no frontmatter block at all."""


def split(text: str) -> tuple[str | None, str]:
    """Split into (frontmatter source, body). Returns ``(None, text)`` when absent.

    The block must open on the very first line, so a ``---`` horizontal rule later in
    the document is body content and is left alone.
    """
    if not text.startswith(_FENCE + "\n") and text.rstrip("\n") != _FENCE:
        return None, text
    rest = text[len(_FENCE) + 1 :]
    end = rest.find("\n" + _FENCE + "\n")
    if rest.startswith(_FENCE + "\n"):
        return "", rest[len(_FENCE) + 1 :]
    if end == -1:
        return None, text
    body = rest[end + len(_FENCE) + 2 :]
    # A blank line between the fence and the prose is conventional, and `render` writes
    # one; it is layout, not content, so exactly one is absorbed here.
    return rest[: end + 1], body[1:] if body.startswith("\n") else body


def parse(text: str) -> tuple[dict[str, Any], str]:
    """Parse a contract file into (frontmatter mapping, body).

    Raises ``MissingFrontmatterError`` when there is no block, and ``MiniYamlError``
    when the block is outside the supported YAML subset.
    """
    front, body = split(text)
    if front is None:
        raise MissingFrontmatterError("no YAML frontmatter block")
    return loads(front), body


def render(data: dict[str, Any], body: str) -> str:
    """Render a mapping and a body back into a contract file."""
    lines: list[str] = []
    _emit_map(lines, data, indent=0)
    front = "".join(lines)
    return f"{_FENCE}\n{front}{_FENCE}\n" + (f"\n{body}" if body else "")


def _emit_map(lines: list[str], data: dict[str, Any], *, indent: int) -> None:
    pad = " " * indent
    for key, value in data.items():
        if isinstance(value, dict) and value:
            lines.append(f"{pad}{key}:\n")
            _emit_map(lines, value, indent=indent + 2)
        elif isinstance(value, list) and value:
            lines.append(f"{pad}{key}:\n")
            _emit_seq(lines, value, indent=indent + 2)
        else:
            lines.append(f"{pad}{key}: {_emit_scalar(value)}\n")


def _emit_seq(lines: list[str], items: list[Any], *, indent: int) -> None:
    pad = " " * indent
    for item in items:
        if isinstance(item, dict) and item:
            nested: list[str] = []
            _emit_map(nested, item, indent=indent + 2)
            lines.append(pad + "- " + nested[0].lstrip())
            lines.extend(nested[1:])
        else:
            lines.append(f"{pad}- {_emit_scalar(item)}\n")


def _emit_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, dict):
        return "{}"
    if isinstance(value, list):
        return "[]"
    text = str(value)
    if _TYPED_LOOKING.match(text) or _needs_quoting(text):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    return text


def _needs_quoting(text: str) -> bool:
    if text != text.strip():
        return True
    if text[0] in "-?:,[]{}#&*!|>'\"%@`":
        return True
    return ": " in text or " #" in text
