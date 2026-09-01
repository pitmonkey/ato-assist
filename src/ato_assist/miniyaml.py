"""A parser for the restricted YAML subset used by every ato-assist file.

Hooks must run against system ``python3`` with no third-party packages, so PyYAML is
unavailable at hook time. If the CLI parsed with PyYAML and the hook parsed with
something else, the hook would deny files the CLI accepts. So both use this.

The subset, deliberately small enough to keep the parser auditable:

* block mappings, nested by indentation (two spaces by convention, any width accepted)
* block sequences (``- item``), including sequences of mappings
* inline sequences ``[a, b]`` and inline mappings ``{a: b}``, nestable
* scalars: bare, single-quoted, double-quoted, ``|`` literal and ``>`` folded blocks
* typed scalars: int, float, ``true``/``false``, ``null``/``~``, ``YYYY-MM-DD`` dates
* ``#`` comments

Everything else is a parse error with a line number, which is itself a validation
finding: "this file uses YAML we do not support" is something an assessor can fix.
Notably absent: anchors and aliases, multiple documents, explicit tags, tab
indentation, timestamps with a time part, and the YAML 1.1 ``yes``/``no``/``on``/``off``
booleans (ambiguous enough that we make you quote them).
"""

from __future__ import annotations

import datetime
import re
from typing import Any, NamedTuple

__all__ = ["MiniYamlError", "loads"]

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(\d+\.\d*|\.\d+)([eE][+-]?\d+)?$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d")
_AMBIGUOUS_BOOL = {"yes", "no", "on", "off", "y", "n"}
_SEQ_MARKER = "\x00-"


class MiniYamlError(ValueError):
    """A construct outside the supported subset, or malformed input."""

    def __init__(self, message: str, line: int) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line
        self.message = message


class _Line(NamedTuple):
    no: int
    indent: int
    text: str


def loads(text: str) -> dict[str, Any]:
    """Parse a document. The top level must be a mapping; an empty document is ``{}``."""
    lines = _scan(text)
    if not lines:
        return {}
    if lines[0].text == _SEQ_MARKER:
        raise MiniYamlError("expected a mapping at the top level, found a sequence", lines[0].no)
    value, index = _parse_map(lines, 0, lines[0].indent)
    if index < len(lines):
        raise MiniYamlError("unexpected indentation", lines[index].no)
    return value


# --- scanning ---------------------------------------------------------------------


def _scan(text: str) -> list[_Line]:
    """Physical lines to logical lines, with ``- `` prefixes expanded into markers.

    A sequence item becomes a bare marker line followed by its value indented two past
    the dash, so ``- ref: X`` nests exactly like a mapping written out longhand and the
    parser needs no special case for "item value starts on the dash line".
    """
    out: list[_Line] = []
    raw_lines = text.split("\n")
    index = 0
    while index < len(raw_lines):
        raw = raw_lines[index]
        no = index + 1
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if "\t" in raw[:indent] or raw.lstrip(" ").startswith("\t"):
            raise MiniYamlError("tab in indentation; use spaces", no)
        if stripped in ("---", "..."):
            raise MiniYamlError("multiple documents are not supported", no)
        content = _strip_comment(raw[indent:], no)
        if not content:
            index += 1
            continue
        _expand(out, no, indent, content)
        index += 1

    _attach_block_scalars(out, raw_lines)
    return out


def _expand(out: list[_Line], no: int, indent: int, content: str) -> None:
    """Emit one logical line, splitting ``- value`` into a marker plus its value."""
    while content == "-" or content.startswith("- "):
        out.append(_Line(no, indent, _SEQ_MARKER))
        if content == "-":
            return
        content = content[2:].lstrip()
        indent += 2
    out.append(_Line(no, indent, content))


def _strip_comment(text: str, no: int) -> str:
    """Drop a trailing ``#`` comment. A ``#`` inside quotes, or not preceded by a space,
    is part of the scalar — which is what keeps ``ref: SRC-0007#anchor`` intact."""
    quote: str | None = None
    for i, char in enumerate(text):
        if quote:
            if char == quote:
                quote = None
            continue
        if char in "\"'":
            quote = char
        elif char == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i].rstrip()
    if quote:
        raise MiniYamlError("unterminated quoted scalar", no)
    return text.rstrip()


def _attach_block_scalars(lines: list[_Line], raw_lines: list[str]) -> None:
    """Replace a ``key: |`` header's value with the folded or literal text below it.

    Block scalar bodies are raw physical lines, so they are collected here from the
    original text rather than from the comment-stripped logical lines.
    """
    for position, line in enumerate(lines):
        key_and_value = _split_key(line.text, line.no) if line.text != _SEQ_MARKER else None
        if key_and_value is None:
            continue
        _, value = key_and_value
        if value not in ("|", ">", "|-", ">-"):
            continue
        body, consumed_to = _collect_block(raw_lines, line.no, line.indent)
        rendered = _render_block(body, style=value[0], chomp=value.endswith("-"))
        lines[position] = _Line(line.no, line.indent, f"{key_and_value[0]}: \x01{rendered}")
        # Drop the logical lines that belonged to the block body.
        while position + 1 < len(lines) and lines[position + 1].no <= consumed_to:
            del lines[position + 1]


def _collect_block(
    raw_lines: list[str], header_no: int, header_indent: int
) -> tuple[list[str], int]:
    body: list[str] = []
    last = header_no
    for offset in range(header_no, len(raw_lines)):
        raw = raw_lines[offset]
        if not raw.strip():
            body.append("")
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent <= header_indent:
            break
        body.append(raw)
        last = offset + 1
    while body and not body[-1].strip():
        body.pop()
    if not body:
        return [], last
    margin = min(len(raw) - len(raw.lstrip(" ")) for raw in body if raw.strip())
    return [raw[margin:] if raw.strip() else "" for raw in body], last


def _render_block(body: list[str], *, style: str, chomp: bool) -> str:
    if not body:
        return ""
    if style == "|":
        text = "\n".join(body)
    else:
        parts: list[str] = []
        for entry in body:
            if not entry:
                parts.append("\n")
            elif parts and not parts[-1].endswith("\n"):
                parts.append(" " + entry)
            else:
                parts.append(entry)
        text = "".join(parts)
    return text if chomp else text + "\n"


# --- parsing ----------------------------------------------------------------------


def _parse_map(lines: list[_Line], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise MiniYamlError("unexpected indentation", line.no)
        if line.text == _SEQ_MARKER:
            break
        split = _split_key(line.text, line.no)
        if split is None:
            raise MiniYamlError("expected 'key: value'", line.no)
        key, value = split
        if key in result:
            raise MiniYamlError(f"duplicate key {key!r}", line.no)
        if value:
            result[key] = _scalar(value, line.no)
            index += 1
        else:
            result[key], index = _parse_nested(lines, index + 1, indent, line.no)
    return result, index


def _parse_nested(lines: list[_Line], index: int, indent: int, header_no: int) -> tuple[Any, int]:
    """The value of a key whose line ended after the colon: a nested block, or null."""
    if index >= len(lines) or lines[index].indent <= indent:
        return None, index
    child = lines[index]
    if child.text == _SEQ_MARKER:
        return _parse_seq(lines, index, child.indent)
    return _parse_map(lines, index, child.indent)


def _parse_seq(lines: list[_Line], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines) and lines[index].indent == indent and lines[index].text == _SEQ_MARKER:
        index += 1
        if index >= len(lines) or lines[index].indent <= indent:
            result.append(None)
            continue
        item = lines[index]
        value: Any
        if item.text == _SEQ_MARKER:
            value, index = _parse_seq(lines, index, item.indent)
        elif _split_key(item.text, item.no) is None:
            value, index = _scalar(item.text, item.no), index + 1
        else:
            value, index = _parse_map(lines, index, item.indent)
        result.append(value)
    return result, index


def _split_key(text: str, no: int) -> tuple[str, str] | None:
    """Split ``key: value`` at the first colon followed by a space or end of line."""
    if text.startswith(("&", "*")):
        raise MiniYamlError("anchors and aliases are not supported", no)
    quote: str | None = None
    for i, char in enumerate(text):
        if quote:
            if char == quote:
                quote = None
            continue
        if char in "\"'":
            quote = char
        elif char in "[{":
            return None
        elif char == ":" and (i + 1 == len(text) or text[i + 1] == " "):
            key = text[:i].strip()
            if key.startswith(("'", '"')) and key.endswith(key[0]) and len(key) > 1:
                key = key[1:-1]
            if not key:
                raise MiniYamlError("empty key", no)
            value = text[i + 1 :].lstrip(" ")
            # A rendered block scalar carries significant trailing newlines; nothing else does.
            return key, value if value.startswith("\x01") else value.strip()
    return None


def _scalar(text: str, no: int) -> Any:
    if text.startswith("\x01"):
        return text[1:]
    if text.startswith(("&", "*")):
        raise MiniYamlError("anchors and aliases are not supported", no)
    if text.startswith("!"):
        raise MiniYamlError("explicit tags are not supported", no)
    if text.startswith("["):
        value, rest = _inline(text, 0, no)
        if rest.strip():
            raise MiniYamlError("trailing content after inline sequence", no)
        return value
    if text.startswith("{"):
        value, rest = _inline(text, 0, no)
        if rest.strip():
            raise MiniYamlError("trailing content after inline mapping", no)
        return value
    return _plain(text, no)


def _plain(text: str, no: int) -> Any:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        body = text[1:-1]
        if text[0] == '"':
            return body.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
        return body.replace("''", "'")
    if text in ("", "null", "~", "Null", "NULL"):
        return None
    if text in ("true", "True", "TRUE"):
        return True
    if text in ("false", "False", "FALSE"):
        return False
    if text.lower() in _AMBIGUOUS_BOOL:
        raise MiniYamlError(f"ambiguous boolean-like scalar {text!r}; quote it", no)
    if _INT_RE.match(text):
        return int(text)
    if _FLOAT_RE.match(text):
        return float(text)
    if _DATE_RE.match(text):
        try:
            return datetime.date.fromisoformat(text)
        except ValueError as exc:
            raise MiniYamlError(f"invalid date {text!r}", no) from exc
    if _TIMESTAMP_RE.match(text):
        raise MiniYamlError("timestamps are not supported; quote it or use a date", no)
    return text


def _inline(text: str, i: int, no: int) -> tuple[Any, str]:
    """Parse one inline collection starting at ``text[i]``; return it and the remainder."""
    opener = text[i]
    closer = "]" if opener == "[" else "}"
    items: list[Any] = []
    pairs: dict[str, Any] = {}
    i += 1
    while True:
        while i < len(text) and text[i] in " \t":
            i += 1
        if i >= len(text):
            kind = "sequence" if opener == "[" else "mapping"
            raise MiniYamlError(f"unterminated inline {kind}", no)
        if text[i] == closer:
            return (items if opener == "[" else pairs), text[i + 1 :]
        chunk, i = _inline_token(text, i, no, closer)
        if opener == "[":
            items.append(chunk)
        else:
            if not isinstance(chunk, str) or ":" not in chunk:
                raise MiniYamlError("expected 'key: value' inside inline mapping", no)
            key, _, value = chunk.partition(":")
            pairs[key.strip()] = _scalar(value.strip(), no)
        while i < len(text) and text[i] in " \t":
            i += 1
        if i < len(text) and text[i] == ",":
            i += 1


def _inline_token(text: str, i: int, no: int, closer: str) -> tuple[Any, int]:
    """One element: a nested collection parsed eagerly, or the raw text up to a delimiter."""
    if text[i] in "[{":
        depth = 0
        quote: str | None = None
        for j in range(i, len(text)):
            char = text[j]
            if quote:
                if char == quote:
                    quote = None
                continue
            if char in "\"'":
                quote = char
            elif char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
                if depth == 0:
                    value, _ = _inline(text[i : j + 1], 0, no)
                    return value, j + 1
        raise MiniYamlError("unterminated inline collection", no)
    start = i
    quote = None
    depth = 0
    while i < len(text):
        char = text[i]
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char in "[{":
            depth += 1
        elif char in "]}" and depth:
            depth -= 1
        elif depth == 0 and (char == "," or char == closer):
            break
        i += 1
    token = text[start:i].strip()
    if closer == "]":
        return _scalar(token, no), i
    return token, i
