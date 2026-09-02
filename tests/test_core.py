"""Smoke tests for groundcheck.core.verify().

Built as one planted-defect corpus (a handful of supported claims
mixed with deliberately broken ones) rather than one test per verdict,
because the bar is exactly that: a checker that flags
everything passes nothing, so the *same* input has to contain both
clean and broken citations for a passing suite to mean anything.

Categories covered, each with 2+ instances:
  - fabricated document id            -> unresolvable
  - out-of-range / malformed span     -> unresolvable
  - span resolves but wrong sentence  -> span-mismatch
  - quote silently reworded           -> span-mismatch (or unresolvable
                                          if reworded past recognition
                                          with no span to anchor it)
  - number in claim differs from src  -> span-mismatch
  - no citation at all                -> uncited
plus >= 4 genuinely supported claims, three of them the *same*
underlying fact expressed as three different surface forms (straight
quotes / curly quotes+dashes / line-wrapped whitespace) to demonstrate
the match survives quoting style rather than having only ever been
tested against one spelling.
"""
import pytest

from groundcheck import verify
from groundcheck.core import (
    VERDICT_SPAN_MISMATCH,
    VERDICT_SUPPORTED,
    VERDICT_UNCITED,
    VERDICT_UNRESOLVABLE,
)

BRIEF = (
    "Acme Corp reported full-year revenue growth of 18% for fiscal 2024, "
    "driven by strong demand in the enterprise segment. Employee headcount "
    "increased from 320 to 401 during the year. The board approved a "
    "budget of $3,400,000 for the new data center. Customer satisfaction "
    "scores averaged 4.6 out of 5 across all regions. The company opened "
    "two new offices, one in Austin and one in Denver."
)

NOTES = (
    "Internal planning notes: the enterprise segment is expected to "
    "represent 70% of bookings next year, up from 55% this year. Legal "
    "review of the Denver lease is still pending."
)

SOURCES = {"brief": BRIEF, "notes": NOTES}

ANSWER = "See the attached fiscal 2024 summary."


def _span(doc, needle):
    start = doc.index(needle)
    return [start, start + len(needle)]


HEADCOUNT_QUOTE = "Employee headcount\nincreased from 320 to 401"
SATISFACTION_QUOTE = "Customer satisfaction\nscores averaged 4.6 out of 5"
BUDGET_QUOTE = "board approved a\nbudget of $3,400,000"
DENVER_SENTENCE_SPAN = _span(BRIEF, "The company opened")
DENVER_SENTENCE_SPAN[1] = len(BRIEF)

CITATIONS = [
    # -- supported: baseline straight-quote form --------------------
    {
        "claim_id": "sup-revenue-straight",
        "text": "Revenue grew 18% in fiscal 2024.",
        "doc_id": "brief",
        "quote": "full-year revenue growth of 18% for fiscal 2024",
    },
    # -- supported: same fact, curly quotes + em dash surface form ---
    {
        "claim_id": "sup-revenue-curly",
        "text": "Revenue grew 18% in fiscal 2024.",
        "doc_id": "brief",
        "quote": "full–year revenue growth of 18% for fiscal 2024",
    },
    # -- supported: same fact, line-wrapped / extra-whitespace form --
    {
        "claim_id": "sup-revenue-wrapped",
        "text": "Revenue grew 18% in fiscal 2024.",
        "doc_id": "brief",
        "quote": "full-year   revenue growth\nof 18%  for fiscal\n2024",
    },
    # -- supported: distinct claim, span-based -----------------------
    {
        "claim_id": "sup-headcount",
        "text": "Headcount increased from 320 to 401 employees.",
        "doc_id": "brief",
        "span": _span(BRIEF, "Employee headcount increased from 320 to 401"),
        "quote": HEADCOUNT_QUOTE,
    },
    # -- supported: distinct claim, quote-only ------------------------
    {
        "claim_id": "sup-satisfaction",
        "text": "Customer satisfaction averaged 4.6 out of 5.",
        "doc_id": "brief",
        "quote": SATISFACTION_QUOTE,
    },
    # -- supported: cross-document claim -------------------------------
    {
        "claim_id": "sup-notes-bookings",
        "text": "The enterprise segment is expected to reach 70% of bookings next year.",
        "doc_id": "notes",
        "quote": "expected to\nrepresent 70% of bookings next year",
    },
    # -- defect: fabricated document id (x2) --------------------------
    {
        "claim_id": "def-fabricated-doc-1",
        "text": "Revenue grew 18% in fiscal 2024.",
        "doc_id": "brief-v2",
        "quote": "full-year revenue growth of 18%",
    },
    {
        "claim_id": "def-fabricated-doc-2",
        "text": "Headcount increased from 320 to 401 employees.",
        "doc_id": "internal-notes-final",
        "span": [0, 10],
    },
    # -- defect: out-of-range / malformed span (x3) -------------------
    {
        "claim_id": "def-span-past-end",
        "text": "The company opened two new offices.",
        "doc_id": "brief",
        "span": [len(BRIEF) - 5, len(BRIEF) + 1],  # one past the end
    },
    {
        "claim_id": "def-span-negative-start",
        "text": "Revenue grew 18% in fiscal 2024.",
        "doc_id": "brief",
        "span": [-1, 20],
    },
    {
        "claim_id": "def-span-zero-length",
        "text": "Revenue grew 18% in fiscal 2024.",
        "doc_id": "brief",
        "span": [10, 10],
    },
    # -- defect: span resolves, wrong sentence (x2) -------------------
    {
        "claim_id": "def-wrong-sentence-1",
        "text": "Headcount increased from 320 to 401 employees.",
        "doc_id": "brief",
        "span": DENVER_SENTENCE_SPAN,  # points at the offices sentence, not headcount
    },
    {
        # note: a span is required to catch a "right document, wrong
        # sentence" defect -- a quote-only citation (no span) only
        # proves the quoted text exists *somewhere* in the document,
        # not that it supports this particular claim's `text` (that
        # would require semantic entailment, which is explicitly out
        # of scope; see README "what this deliberately does not do").
        "claim_id": "def-wrong-sentence-2",
        "text": "The board approved a budget for the new data center.",
        "doc_id": "brief",
        "span": _span(BRIEF, "Customer satisfaction scores averaged 4.6 out of 5"),
    },
    # -- defect: quote silently reworded (x2) --------------------------
    {
        "claim_id": "def-reworded-quote-with-span",
        "text": "Customer satisfaction averaged 4.9 out of 5.",
        "doc_id": "brief",
        "span": _span(BRIEF, "Customer satisfaction scores averaged 4.6 out of 5"),
        "quote": "Customer satisfaction\nscores averaged 4.9 out of 5",  # 4.9 vs real 4.6
    },
    {
        "claim_id": "def-reworded-quote-no-span",
        "text": "The board approved a budget of $9,000,000.",
        "doc_id": "brief",
        "quote": "board approved a budget of $9,000,000",  # not present anywhere -> unresolvable
    },
    # -- defect: claim number differs from source (x2) -----------------
    {
        "claim_id": "def-number-mismatch-explicit",
        "text": "The board approved a budget of $3,500,000 for the data center.",
        "doc_id": "brief",
        "quote": BUDGET_QUOTE,  # quote itself is accurate; `text` states a different figure
    },
    {
        "claim_id": "def-number-mismatch-span",
        "text": "Headcount increased from 320 to 402 employees.",
        "doc_id": "brief",
        "span": _span(BRIEF, "Employee headcount increased from 320 to 401"),
    },
    # -- defect: no citation at all (x2) --------------------------------
    {
        "claim_id": "def-uncited-missing-key",
        "text": "The company opened two new offices this year.",
    },
    {
        "claim_id": "def-uncited-explicit-none",
        "text": "Customer satisfaction averaged 4.6 out of 5.",
        "doc_id": None,
    },
]

EXPECTED = {
    "sup-revenue-straight": VERDICT_SUPPORTED,
    "sup-revenue-curly": VERDICT_SUPPORTED,
    "sup-revenue-wrapped": VERDICT_SUPPORTED,
    "sup-headcount": VERDICT_SUPPORTED,
    "sup-satisfaction": VERDICT_SUPPORTED,
    "sup-notes-bookings": VERDICT_SUPPORTED,
    "def-fabricated-doc-1": VERDICT_UNRESOLVABLE,
    "def-fabricated-doc-2": VERDICT_UNRESOLVABLE,
    "def-span-past-end": VERDICT_UNRESOLVABLE,
    "def-span-negative-start": VERDICT_UNRESOLVABLE,
    "def-span-zero-length": VERDICT_UNRESOLVABLE,
    "def-wrong-sentence-1": VERDICT_SPAN_MISMATCH,
    "def-wrong-sentence-2": VERDICT_SPAN_MISMATCH,
    "def-reworded-quote-with-span": VERDICT_SPAN_MISMATCH,
    "def-reworded-quote-no-span": VERDICT_UNRESOLVABLE,
    "def-number-mismatch-explicit": VERDICT_SPAN_MISMATCH,
    "def-number-mismatch-span": VERDICT_SPAN_MISMATCH,
    "def-uncited-missing-key": VERDICT_UNCITED,
    "def-uncited-explicit-none": VERDICT_UNCITED,
}


@pytest.fixture(scope="module")
def report():
    return verify(answer=ANSWER, citations=CITATIONS, sources=SOURCES)


def test_every_claim_gets_the_expected_verdict(report):
    by_id = {cv.claim_id: cv.verdict for cv in report.claims}
    mismatches = {cid: (by_id[cid], expected) for cid, expected in EXPECTED.items() if by_id[cid] != expected}
    assert mismatches == {}


def test_at_least_four_supported_claims_present(report):
    supported = [c for c in report.claims if c.verdict == VERDICT_SUPPORTED]
    assert len(supported) >= 4


def test_at_least_twelve_defects_present(report):
    defects = [c for c in report.claims if c.verdict != VERDICT_SUPPORTED]
    assert len(defects) >= 12


def test_all_four_verdict_kinds_appear(report):
    seen = {c.verdict for c in report.claims}
    assert seen == {VERDICT_SUPPORTED, VERDICT_SPAN_MISMATCH, VERDICT_UNRESOLVABLE, VERDICT_UNCITED}


def test_number_mismatch_reason_is_reachable_not_dead_code(report):
    by_id = {cv.claim_id: cv for cv in report.claims}
    assert by_id["def-number-mismatch-explicit"].reason == "number_mismatch"


def test_counts_match_claim_tally(report):
    d = report.to_dict()
    assert d["counts"]["total"] == len(CITATIONS)
    tally = {"supported": 0, "span-mismatch": 0, "unresolvable": 0, "uncited": 0}
    for c in d["claims"]:
        tally[c["verdict"]] += 1
    for k, v in tally.items():
        assert d["counts"][k] == v


def test_failing_claim_ids_excludes_only_supported(report):
    failing = set(report.failing_claim_ids)
    for cv in report.claims:
        assert (cv.claim_id in failing) == (cv.verdict != VERDICT_SUPPORTED)


def test_exit_code_is_1_because_unresolvable_present(report):
    assert report.exit_code == 1


def test_exit_code_is_0_when_no_unresolvable_claim():
    clean = [c for c in CITATIONS if EXPECTED[c["claim_id"]] != VERDICT_UNRESOLVABLE]
    r = verify(answer=ANSWER, citations=clean, sources=SOURCES)
    assert r.counts["unresolvable"] == 0
    assert r.exit_code == 0


def test_corrupting_a_source_flips_supported_to_span_mismatch():
    """Gate: the checker must be able to go red. Corrupt the source
    document backing a previously-supported claim and require the
    verdict to flip."""
    good = verify(
        answer=ANSWER,
        citations=[{"claim_id": "c", "doc_id": "brief", "quote": "full-year revenue growth of 18%"}],
        sources=SOURCES,
    )
    assert good.claims[0].verdict == VERDICT_SUPPORTED

    corrupted_sources = dict(SOURCES)
    corrupted_sources["brief"] = BRIEF.replace("18%", "99%")
    bad = verify(
        answer=ANSWER,
        citations=[{"claim_id": "c", "doc_id": "brief", "quote": "full-year revenue growth of 18%"}],
        sources=corrupted_sources,
    )
    assert bad.claims[0].verdict != VERDICT_SUPPORTED


def test_claim_id_auto_assigned_when_omitted():
    r = verify(answer="x", citations=[{"text": "x", "doc_id": "brief", "quote": "Acme Corp"}], sources=SOURCES)
    assert r.claims[0].claim_id == "claim-000"


def test_claims_report_sorted_by_claim_id_regardless_of_input_order():
    citations = [
        {"claim_id": "zzz", "text": "x", "doc_id": "brief", "quote": "Acme Corp"},
        {"claim_id": "aaa", "text": "x", "doc_id": "brief", "quote": "Acme Corp"},
    ]
    r = verify(answer="x", citations=citations, sources=SOURCES)
    assert [c.claim_id for c in r.claims] == ["aaa", "zzz"]


def test_answer_span_derives_claim_text_when_text_omitted():
    answer = "Revenue grew 18% this year."
    citations = [
        {
            "claim_id": "c",
            "answer_span": [0, len("Revenue grew 18% this year.") - 1],
            "doc_id": "brief",
            "quote": "full-year revenue growth of 18%",
        }
    ]
    r = verify(answer=answer, citations=citations, sources=SOURCES)
    assert r.claims[0].verdict == VERDICT_SUPPORTED


def test_malformed_citations_argument_raises():
    from groundcheck.core import GroundcheckError

    with pytest.raises(GroundcheckError):
        verify(answer="x", citations="not-a-list", sources=SOURCES)


def test_malformed_sources_argument_raises():
    from groundcheck.core import GroundcheckError

    with pytest.raises(GroundcheckError):
        verify(answer="x", citations=[], sources=["not", "a", "mapping"])


def test_malformed_span_shape_is_unresolvable_not_a_crash():
    r = verify(
        answer="x",
        citations=[{"claim_id": "c", "text": "x", "doc_id": "brief", "span": [1, 2, 3]}],
        sources=SOURCES,
    )
    assert r.claims[0].verdict == VERDICT_UNRESOLVABLE
    assert r.claims[0].reason == "malformed_span"


def test_citation_with_neither_span_nor_quote_is_unresolvable():
    r = verify(
        answer="x",
        citations=[{"claim_id": "c", "text": "x", "doc_id": "brief"}],
        sources=SOURCES,
    )
    assert r.claims[0].verdict == VERDICT_UNRESOLVABLE
    assert r.claims[0].reason == "no_anchor"
