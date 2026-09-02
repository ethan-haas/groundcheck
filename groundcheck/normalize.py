"""Deterministic text normalization used for span/quote comparison.

Everything here is pure string manipulation over the standard library.
No locale, no time, no randomness -- same input always yields the same
output, in any process, on any machine.
"""
from __future__ import annotations

import re
import unicodedata

# Unicode punctuation that commonly differs between an answer's quoting
# style and a source document's -- curly quotes, en/em dashes, ellipsis,
# non-breaking space -- collapsed to a single ASCII form so that quoting
# style alone never causes a false span-mismatch.
_PUNCT_TRANSLATION = str.maketrans(
    {
        "‘": "'",  # left single quote
        "’": "'",  # right single quote
        "‚": "'",  # single low-9 quote
        "′": "'",  # prime
        "“": '"',  # left double quote
        "”": '"',  # right double quote
        "„": '"',  # double low-9 quote
        "″": '"',  # double prime
        "–": "-",  # en dash
        "—": "-",  # em dash
        "−": "-",  # minus sign
        "…": "...",  # ellipsis
        " ": " ",  # non-breaking space
        "​": "",  # zero-width space
        "﻿": "",  # BOM
    }
)

_WHITESPACE_RE = re.compile(r"\s+")

# Punctuation that terminates a sentence/clause and is routinely
# present on one side of a comparison and absent on the other purely
# because of where a caller's span or quote happened to be cut (e.g. a
# claim's `text` field ends in a period because it is a full sentence,
# while the cited `span` stops one character earlier, right at the
# last word). Trimmed only from the ends of the normalized string, so
# it never touches punctuation that is actually part of the compared
# content (a sentence in the *middle* of a span keeps its period).
_EDGE_PUNCT = " \t\n.,;:!?\"'"


def normalize(text: str | None) -> str:
    """Canonicalize text for deterministic comparison.

    Steps (all order-independent of machine/locale, all deterministic):
      1. Unicode NFKC normalization (compatibility forms -> canonical).
      2. Unify curly quotes / dashes / ellipsis / NBSP to ASCII.
      3. Collapse all whitespace runs (spaces, tabs, newlines -- this is
         what makes line-wrapped source text compare equal to unwrapped
         quoted text) to a single space.
      4. Strip leading/trailing whitespace.
      5. Casefold for case-insensitive comparison.
      6. Trim leading/trailing sentence punctuation (see `_EDGE_PUNCT`)
         so a claim text's terminal period does not, by itself, make
         it fail to match a span that was cut one character short.

    Two byte-identical inputs always normalize identically; two
    differently-encoded-but-equivalent inputs (curly vs straight quotes,
    wrapped vs unwrapped) normalize to the same string.
    """
    if not text:
        return ""
    out = unicodedata.normalize("NFKC", text)
    out = out.translate(_PUNCT_TRANSLATION)
    out = _WHITESPACE_RE.sub(" ", out)
    out = out.strip()
    out = out.casefold()
    out = out.strip(_EDGE_PUNCT)
    return out


# A number token: optional sign, optional currency symbol, digit groups
# with optional thousands separators, optional decimal part, optional
# percent sign. Deliberately permissive on input, canonicalized on output.
_NUMBER_RE = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?%?")


def extract_numbers(text: str | None) -> frozenset[str]:
    """Extract every numeric token from `text`, canonicalized.

    Canonicalization strips thousands separators and the currency
    symbol so "$1,234" and "1234" compare equal, but keeps a percent
    sign attached since "12" and "12%" are different assertions.
    Returns a frozenset (order never matters for comparison, and a
    frozenset sorts out any duplicate-token ambiguity deterministically
    when later rendered via ``sorted()``).
    """
    if not text:
        return frozenset()
    out = set()
    for match in _NUMBER_RE.finditer(text):
        token = match.group(0)
        canon = token.replace(",", "").replace("$", "").strip()
        if canon in ("", "-", "+"):
            continue
        out.add(canon)
    return frozenset(out)
