"""groundcheck core: verify claims against cited source spans.

Contract (see README for the full write-up):

    report = groundcheck.verify(answer=..., citations=[...], sources={...})

`citations` is a list where each element describes exactly one claim
made in `answer`. There is deliberately no separate `claims` argument:
a claim and its citation are one record, because the property this
library checks is "is this specific assertion backed by this specific
citation" -- splitting them into parallel lists just invites the two
lists going out of sync.

Each citation record is a dict with these keys, ALL optional except
where noted:

    text          str  -- the claim's asserted content, in the caller's
                           own words or verbatim. Required unless
                           `answer_span` is given instead.
    answer_span   [start, end] -- if `text` is omitted, the claim text
                           is sliced out of `answer` at these offsets.
    claim_id      str  -- stable id for this claim. Auto-assigned as
                           "claim-000", "claim-001", ... (input order,
                           zero-padded) if omitted.
    doc_id        str  -- id of the cited source document, a key into
                           `sources`. Omitted or falsy -> verdict is
                           "uncited"; every other field is ignored.
    span          [start, end] -- character offsets into
                           sources[doc_id], Python half-open slice
                           convention (0-indexed, end exclusive, so
                           sources[doc_id][start:end] is the cited
                           text). Out-of-range or malformed offsets
                           are a hard failure (unresolvable), never a
                           silent clamp.
    quote         str  -- the exact text the citation claims appears
                           in the source at/around `span`. If `span`
                           is omitted, `quote` is instead searched for
                           (normalized) anywhere in the source document
                           and its presence establishes the citation's
                           anchor. If both are given, `span` supplies
                           the location and `quote` supplies the
                           expected content at that location -- so a
                           quote that has been silently reworded from
                           what is actually at that span is caught
                           even though the span itself resolves fine.

Verdicts (exactly one per input citation record, same order preserved
via claim_id):

    supported      -- doc_id resolves, span/quote resolves to real
                       text in the document, and that text contains
                       the claim's asserted content (see "containment"
                       below).
    span-mismatch  -- doc_id and span/quote both resolve to *some*
                       real text, but that text does not contain the
                       claim's asserted content, OR the claim asserts
                       a number that the resolved text does not
                       contain.
    unresolvable   -- doc_id is not in `sources`, OR span offsets are
                       out of range / malformed, OR a quote-only
                       citation's quote cannot be found anywhere in
                       the document, OR the citation supplies neither
                       span nor quote. Always a hard failure.
    uncited        -- doc_id is missing/empty/None. No further checks
                       are performed.

"Containment" is defined mechanically, not semantically: after
`normalize()` (see normalize.py) is applied to both sides, the
expected content (the `quote` if given, else `text`) must appear as a
substring of the resolved evidence text. This is deliberately a dumb,
readable, exact-after-normalization check -- not a paraphrase judge --
because the whole point of this library is a narrow, explainable
contract instead of a model-in-the-loop guess.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from .normalize import extract_numbers, normalize

VERDICT_SUPPORTED = "supported"
VERDICT_SPAN_MISMATCH = "span-mismatch"
VERDICT_UNRESOLVABLE = "unresolvable"
VERDICT_UNCITED = "uncited"

ALL_VERDICTS = (
    VERDICT_SUPPORTED,
    VERDICT_SPAN_MISMATCH,
    VERDICT_UNRESOLVABLE,
    VERDICT_UNCITED,
)


class GroundcheckError(ValueError):
    """Raised for malformed input that is a caller bug, not a claim defect

    (e.g. `citations` is not a list, or `sources` is not a mapping).
    A citation record's own internal malformedness -- a span that is
    not a 2-tuple, say -- is NOT raised; it is reported as an
    "unresolvable" verdict on that one claim, because one bad citation
    record should never crash a batch verification of N claims.
    """


@dataclass(frozen=True)
class ClaimVerdict:
    claim_id: str
    verdict: str
    doc_id: Optional[str] = None
    reason: Optional[str] = None
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "verdict": self.verdict,
            "doc_id": self.doc_id,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class VerificationReport:
    claims: tuple  # tuple[ClaimVerdict, ...], sorted by claim_id
    counts: dict
    failing_claim_ids: tuple

    @property
    def exit_code(self) -> int:
        """1 iff any claim is unresolvable, else 0.

        Only `unresolvable` forces a non-zero exit: the one hard
        rule is that an unverifiable citation must never be a silent
        warning. `span-mismatch` and `uncited` are real findings and
        are always included in `failing_claim_ids` / counts, but they
        are not, by themselves, grounds to fail a CI job that is
        gating on "can every citation even be resolved" -- a caller
        who wants a stricter gate can inspect `counts` directly (see
        README "CLI / exit codes").
        """
        return 1 if self.counts.get(VERDICT_UNRESOLVABLE, 0) > 0 else 0

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "counts": dict(sorted(self.counts.items())),
            "claims": [c.to_dict() for c in self.claims],
            "failing_claim_ids": list(self.failing_claim_ids),
        }

    def to_json(self, indent: int = 2) -> str:
        # sort_keys=True + explicit list ordering above is what makes
        # this byte-identical across processes: nothing here depends
        # on dict/set iteration order, hash randomization, locale, or
        # wall-clock time.
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, ensure_ascii=False) + "\n"


def verify(
    answer: str,
    citations: Sequence[Mapping[str, Any]],
    sources: Mapping[str, str],
) -> VerificationReport:
    """Verify every claim in `citations` against `sources`. See module
    docstring for the full record shape and verdict definitions.
    """
    if not isinstance(citations, Sequence) or isinstance(citations, (str, bytes)):
        raise GroundcheckError("citations must be a list of citation records")
    if not isinstance(sources, Mapping):
        raise GroundcheckError("sources must be a mapping of doc_id -> text")

    verdicts = []
    width = max(3, len(str(max(len(citations) - 1, 0))))
    for index, record in enumerate(citations):
        if not isinstance(record, Mapping):
            raise GroundcheckError(f"citation at index {index} is not a mapping/dict")
        claim_id = record.get("claim_id") or f"claim-{index:0{width}d}"
        verdicts.append(_verify_one(claim_id, index, record, answer, sources))

    claims_sorted = tuple(sorted(verdicts, key=lambda v: v.claim_id))
    counts = {v: 0 for v in ALL_VERDICTS}
    for cv in claims_sorted:
        counts[cv.verdict] += 1
    counts["total"] = len(claims_sorted)
    failing = tuple(
        sorted(cv.claim_id for cv in claims_sorted if cv.verdict != VERDICT_SUPPORTED)
    )
    return VerificationReport(claims=claims_sorted, counts=counts, failing_claim_ids=failing)


def _verify_one(
    claim_id: str,
    index: int,
    record: Mapping[str, Any],
    answer: str,
    sources: Mapping[str, str],
) -> ClaimVerdict:
    text = record.get("text")
    if text is None:
        answer_span = record.get("answer_span")
        if answer_span is not None:
            try:
                a_start, a_end = answer_span
                text = (answer or "")[a_start:a_end]
            except (TypeError, ValueError):
                text = ""
        else:
            text = ""

    doc_id = record.get("doc_id")
    if not doc_id:
        return ClaimVerdict(
            claim_id, VERDICT_UNCITED, doc_id=None,
            reason="no_citation", detail="claim carries no citation",
        )

    if doc_id not in sources:
        return ClaimVerdict(
            claim_id, VERDICT_UNRESOLVABLE, doc_id=doc_id,
            reason="unknown_document",
            detail=f"document id {doc_id!r} is not present in sources",
        )
    doc_text = sources[doc_id]

    span = record.get("span")
    quote = record.get("quote")
    evidence = None

    if span is not None:
        if not (isinstance(span, (list, tuple)) and len(span) == 2):
            return ClaimVerdict(
                claim_id, VERDICT_UNRESOLVABLE, doc_id=doc_id,
                reason="malformed_span",
                detail=f"span {span!r} is not a 2-element [start, end]",
            )
        start, end = span
        valid_ints = isinstance(start, int) and isinstance(end, int) and not isinstance(start, bool) and not isinstance(end, bool)
        if not valid_ints or start < 0 or end <= start or end > len(doc_text):
            return ClaimVerdict(
                claim_id, VERDICT_UNRESOLVABLE, doc_id=doc_id,
                reason="invalid_span",
                detail=(
                    f"span [{start!r}, {end!r}] is out of range for "
                    f"document {doc_id!r} of length {len(doc_text)}"
                ),
            )
        evidence = doc_text[start:end]

    if evidence is None and quote:
        norm_doc = normalize(doc_text)
        norm_quote = normalize(quote)
        if not norm_quote or norm_quote not in norm_doc:
            return ClaimVerdict(
                claim_id, VERDICT_UNRESOLVABLE, doc_id=doc_id,
                reason="quote_not_found",
                detail="quote could not be located anywhere in the cited document",
            )
        # The anchor is document-level (we know the quote occurs
        # *somewhere* in the doc, but not exactly where, since no span
        # was given), so `evidence` is the whole document rather than
        # the quote parroted back at itself -- using the quote as its
        # own "evidence" would make every subsequent check a tautology
        # (a string trivially contains itself) and would starve the
        # number-mismatch check of surrounding context that a real
        # span would have included. A caller who wants a tighter,
        # span-scoped number check should supply `span` alongside
        # `quote`.
        evidence = doc_text

    if evidence is None:
        return ClaimVerdict(
            claim_id, VERDICT_UNRESOLVABLE, doc_id=doc_id,
            reason="no_anchor",
            detail="citation supplies neither a span nor a quote to anchor it",
        )

    # `quote`, when present, is the authoritative expected content --
    # it is what a "silently reworded quote" defect corrupts, and it
    # is checked against the *actually resolved* evidence text even
    # when a span also resolved it, so a reworded quote is caught even
    # though its span offsets are perfectly valid.
    expected = quote if quote else text
    norm_evidence = normalize(evidence)
    norm_expected = normalize(expected)
    if norm_expected and norm_expected not in norm_evidence:
        return ClaimVerdict(
            claim_id, VERDICT_SPAN_MISMATCH, doc_id=doc_id,
            reason="content_not_in_span",
            detail="the cited text does not contain the claim's asserted content",
        )

    # Independent of the containment check above: the human-readable
    # `text` of the claim can assert a number that disagrees with the
    # source even when the `quote` field (checked above) is itself an
    # accurate excerpt -- e.g. a caller pastes the right supporting
    # sentence into `quote` but a wrong figure into `text`. Comparing
    # `text`'s numbers against `evidence` (not against `expected`,
    # which would just re-check `quote` against itself) is what makes
    # this branch reachable rather than dead code shadowed by the
    # containment check.
    claim_numbers = extract_numbers(text)
    evidence_numbers = extract_numbers(evidence)
    missing = sorted(n for n in claim_numbers if n not in evidence_numbers)
    if missing:
        return ClaimVerdict(
            claim_id, VERDICT_SPAN_MISMATCH, doc_id=doc_id,
            reason="number_mismatch",
            detail=f"claim asserts number(s) {missing} not present in the cited text",
        )

    return ClaimVerdict(claim_id, VERDICT_SUPPORTED, doc_id=doc_id, reason=None, detail="")
