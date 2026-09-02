# groundcheck

**The contract:** every claim in an answer is verified against its citation and
gets exactly one verdict:

| Verdict | Meaning |
|---|---|
| `supported` | the citation resolves to real text in the named document, and that text contains the claim's asserted content. |
| `span-mismatch` | the citation resolves to real text, but that text does not contain what the claim asserts (wrong sentence, reworded quote, or a number the claim states that the cited text does not). |
| `unresolvable` | the citation cannot be resolved at all: unknown document id, out-of-range/malformed span, or a quote that cannot be found anywhere in the document. **This is always a hard failure, never a warning.** |
| `uncited` | the claim carries no citation. |

**Exit-code behaviour (the CI-gate contract):** the CLI exits **non-zero if and
only if at least one claim is `unresolvable`**. `span-mismatch` and `uncited`
are real findings and are always in the report's `failing_claim_ids`, but by
themselves they do not fail the process -- an unresolvable citation is the one
thing this library refuses to let slide silently, because a pipeline that
cannot even locate what it cited is not a pipeline you can trust the rest of
the report from. If your gate wants to be stricter, read `counts` yourself:

```python
report = groundcheck.verify(answer=answer, citations=citations, sources=sources)
if report.counts["span-mismatch"] or report.counts["uncited"]:
    ...  # your own, stricter policy
```

## Quickstart (no setup, no network)

```bash
python examples/quickstart.py
```

reads the vendored `examples/input.json` and `examples/docs/` and prints the
report. Equivalently, from the command line once installed:

```bash
pip install -e .
python -m groundcheck.cli examples/input.json --sources examples/docs
# or, if the installed console-script entry point is on PATH:
groundcheck examples/input.json --sources examples/docs
```

**Both of those exit `1`, on purpose.** The vendored example is a detection
demo, not a clean input. Six claims: two genuinely supported, and four
planted defects -- an uncited claim, a silently reworded quote, a stated
number the cited text does not contain, and a citation to a document that
does not exist. Exit `1` means the checker found them, so an example that
exited `0` would be the broken one. The two supported claims are the other
half of the test: a checker that flagged everything would pass nothing.

## Library API

```python
import groundcheck

report = groundcheck.verify(
    answer="Revenue grew 12% in fiscal 2023.",
    citations=[
        {
            "claim_id": "revenue-growth",       # optional; auto-assigned "claim-000" etc. if omitted
            "text": "Revenue grew 12% in fiscal 2023.",   # the claim's asserted content
            "doc_id": "quarterly-brief",         # key into `sources`; omit/None -> verdict "uncited"
            "span": [140, 175],                  # optional: [start, end) offsets into sources[doc_id]
            "quote": "revenue growth of 12%",     # optional: exact text expected at/near `span`
        },
        # ... one record per claim
    ],
    sources={"quarterly-brief": "... full document text ..."},
)

report.counts               # {"supported": 1, "span-mismatch": 0, "unresolvable": 0, "uncited": 0, "total": 1}
report.claims                # tuple[ClaimVerdict, ...], sorted by claim_id
report.failing_claim_ids     # tuple of claim_ids where verdict != "supported"
report.exit_code             # 1 iff any claim is "unresolvable", else 0
report.to_dict() / .to_json()  # the machine-readable report
```

Every field on a citation record except `text` (or `answer_span`, see below)
is optional -- see `groundcheck/core.py`'s module docstring for the complete,
authoritative field-by-field contract. The short version:

- Give **`doc_id`** or the claim is `uncited`, full stop; nothing else is checked.
- Give **`span`** (offset-based resolution) and/or **`quote`** (exact-text
  matching) to anchor the citation. You can give either or both:
  - `span` only: the claim's `text` itself is checked against exactly the
    text at that span. Precise, but brittle if `text` is a loose paraphrase.
  - `quote` only: `quote` is searched for (normalized) anywhere in the
    document. Looser positionally, but only tells you the quoted text
    *exists somewhere* in the doc -- it cannot catch a citation that points
    (or would point) at the wrong sentence, because there's no span to be
    wrong about. Use `span` too if you need that.
  - both: `span` supplies the location, `quote` supplies the expected
    content there. This is what catches a **silently reworded quote**: the
    span offsets are perfectly valid, but the text actually sitting at
    that span doesn't match what `quote` claims it says.
- If neither `span` nor `quote` is given, the citation is `unresolvable`
  (`reason: "no_anchor"`) -- a citation that points at nothing is exactly the
  kind of thing this library exists to catch, not silently pass.

### Design decisions worth stating outright

- **Containment is normalized-substring, not semantic entailment.** After
  `normalize()` (Unicode NFKC, curly-quote/dash unification, whitespace
  collapse across line wraps, casefold, edge-punctuation trim), the expected
  content must appear as a literal substring of the resolved evidence text.
  This is a deliberately dumb, readable, mechanical check -- it is not a
  paraphrase judge, on purpose (see "out of scope" below).
- **Number-assertion mismatches** get their own `reason: "number_mismatch"`
  (a `span-mismatch` verdict) whenever the claim's numbers aren't literally
  present in the compared text, so a caller can distinguish "wrong number"
  from "wrong sentence" diagnostically, even though the underlying verdict
  is the same either way.
- **Off-by-one spans are `unresolvable`, not `span-mismatch`.** A span whose
  offsets fall (even by one character) outside `[0, len(document_text)]`, or
  where `end <= start`, cannot be resolved to any real slice of text at all
  -- that is a different failure mode than "the span resolved to real text
  but it's the wrong text", so it gets the different verdict.
- **Quote-only citations verify document-level, not span-level.** A citation
  with only `quote` (no `span`) has its evidence set to the *whole* document,
  not the quote parroted back at itself -- otherwise the containment check
  becomes a self-referential tautology. This is why "right document, wrong
  sentence" defects need `span` to be catchable; a quote-only citation can
  only prove the quoted text exists somewhere in the doc.

## What this deliberately does not do (out of scope)

- **Not a retrieval framework.** It does not fetch, rank, or chunk documents.
  You hand it `sources` already resolved to text.
- **Not a judge.** It does not score answer quality, fluency, or whether the
  overall answer is "good" -- only whether each individual citation holds.
- **No semantic/paraphrase matching.** A claim whose wording diverges enough
  from its source that normalized-substring containment fails will be
  `span-mismatch` even if a human would call it a fair paraphrase. This is
  the trade-off for being deterministic and explainable with zero model in
  the loop; see the `quote` field if your caller wants a looser anchor with
  a tighter, separately-checked exact-text expectation.
- **No provider SDKs, no network, no model, no API key -- in any code path,
  including the test suite.** Every test in `tests/` runs entirely offline
  against inline or vendored fixtures.

## Determinism across processes

`verify()` and `VerificationReport.to_json()` never depend on dict/set
iteration order: claims are always sorted by `claim_id` before being placed
in the report, `counts` keys are sorted before serialization, and
`json.dumps(..., sort_keys=True)` sorts everything else. There is no
`time.time()`, no `random`, no filesystem/network access, and no reliance on
`PYTHONHASHSEED`-sensitive iteration anywhere in the library. `tests/test_determinism.py`
asserts this directly by running the same input in three independent `python
-m` subprocesses (each free to pick its own random hash seed) and diffing
their stdout byte-for-byte.

## CLI

```
groundcheck INPUT.json --sources DOCS_DIR [--out OUTPUT.json]
```

`INPUT.json` is `{"answer": "...", "citations": [...]}`. `DOCS_DIR` is a flat
directory of source documents, one file per `doc_id` (a file named `foo.txt`
or `foo` both resolve to `doc_id` `"foo"`). The full report JSON is printed to
stdout (and, if `--out` is given, also written there). Exit codes: `0` clean,
`1` at least one `unresolvable` claim, `2` malformed input/usage (bad JSON,
missing `--sources` directory) -- kept distinct from `1` so a CI pipeline can
tell "your citations have a defect" apart from "your input file is broken."

## Development

```bash
pip install -e .
python -m pytest tests/ -q
```

No dependencies beyond the standard library and (for the test suite) `pytest`.
