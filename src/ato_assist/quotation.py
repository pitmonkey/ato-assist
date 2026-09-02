"""What "verbatim" means, in one place.

A quote is taken from a document as the document reads. The chunk it is checked against is
what a converter produced, and that carries things the document never had: grid-table
borders breaking a sentence across cells, and markdown escapes in front of ordinary
punctuation. A quote that reads as the document reads is right, and comparing it to the
raw conversion would fail a correct claim — 46 of 135, in the assessment that found this.

So one function reconciles the two, and everything that compares a quote goes through it.
If the definition ever needs to change it changes here, rather than diverging between a
check that enforces one thing and a skill that describes another.

What it does not do: `sources/` stays byte-faithful. The conversion's output is the record
of what the converter actually produced, and rewriting it would make that unknowable. The
reconciliation happens at comparison time, which also means it works on documents ingested
before any of this existed.
"""

from __future__ import annotations

import re

__all__ = ["contains", "flatten"]

# A row of +---+===+ characters: table drawing, never content.
_BORDER = re.compile(r"^\s*[+|][-=+|\s]*$")
# A leading or trailing cell pipe. A pipe inside a sentence is content and is left alone.
_EDGE_PIPE = re.compile(r"^\s*\|\s?|\s?\|\s*$")
# A converter escapes punctuation, never letters or digits: `\'` is an apostrophe,
# `C:\node` is a path. Spelled out rather than [^\w\s], because `_` is a word character
# to `re` and `\_` is exactly what a converter emits for an underscore.
_ESCAPE = re.compile(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])")


def flatten(text: str) -> str:
    """Text as the document reads it: no table rendering, no escaping, no wrapping.

    Pipes at the edge of a line are cell walls and go; a pipe inside a line stays, because
    a column separator and a pipe in a sentence are indistinguishable and mangling prose
    is the worse error. A quote spanning two columns of one row will therefore not match —
    which is correct, since such a quote is not a sentence the document contains.
    """
    cleaned = [
        " ".join(_ESCAPE.sub(r"\1", _EDGE_PIPE.sub("", line)).split())
        for line in text.splitlines()
        if not _BORDER.match(line)
    ]
    return " ".join(part for part in cleaned if part).strip()


def contains(haystack: str, quote: str) -> bool:
    """Whether ``quote`` appears in ``haystack``, both read as the document reads them."""
    flat_quote = flatten(quote)
    return bool(flat_quote) and flat_quote in flatten(haystack)
