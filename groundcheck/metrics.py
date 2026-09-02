"""Two-sided refusal scoring for a labelled evaluation corpus.

Not part of the verification contract itself -- `verify()` never calls
into this module. This is a small, separate utility for anyone
building an evaluation harness against groundcheck (which is exactly
how this library's own test suite uses it): given a labelled set of
claims where you know ahead of time which ones are genuinely
supported and which are planted defects, compute the two distinct
numbers kept separate, never blended into one accuracy:

    false_flag_rate   -- of the claims that were genuinely supported,
                          the fraction verify() did NOT call
                          "supported" (a checker that flags everything
                          scores 1.0 here and is useless).
    missed_defect_rate -- of the claims that were planted defects, the
                          fraction verify() called "supported" anyway
                          (a checker that never fires scores 1.0 here
                          and is equally useless).

A good checker drives both toward 0 independently; neither number can
compensate for the other, by construction (they are computed over
disjoint subsets of the labelled set).
"""
from __future__ import annotations

from typing import Iterable, Mapping

from .core import VERDICT_SUPPORTED


def two_sided_score(
    verdicts_by_claim_id: Mapping[str, str],
    expected_supported_claim_ids: Iterable[str],
    expected_defect_claim_ids: Iterable[str],
) -> dict:
    """Compute false_flag_rate and missed_defect_rate over a labelled set.

    `verdicts_by_claim_id`: claim_id -> verdict string, as produced by
        `{cv.claim_id: cv.verdict for cv in report.claims}`.
    `expected_supported_claim_ids`: claim_ids the labeller asserts are
        genuinely, correctly cited (no defect planted).
    `expected_defect_claim_ids`: claim_ids the labeller asserts have a
        planted defect of some kind (any non-"supported" verdict is a
        correct catch; the specific verdict/reason is not compared
        here on purpose -- that is a matter for a stricter per-defect-
        type audit than this two-number gate calls for).

    Raises ValueError if the two label sets overlap (a claim cannot be
    both a labelled-clean example and a labelled-defect example), or if
    a labelled claim_id is missing from `verdicts_by_claim_id`.
    """
    supported_ids = frozenset(expected_supported_claim_ids)
    defect_ids = frozenset(expected_defect_claim_ids)
    overlap = supported_ids & defect_ids
    if overlap:
        raise ValueError(f"claim_ids labelled as both supported and defect: {sorted(overlap)}")

    missing = (supported_ids | defect_ids) - verdicts_by_claim_id.keys()
    if missing:
        raise ValueError(f"labelled claim_ids not present in verdicts: {sorted(missing)}")

    if supported_ids:
        false_flags = sum(
            1 for cid in supported_ids if verdicts_by_claim_id[cid] != VERDICT_SUPPORTED
        )
        false_flag_rate = false_flags / len(supported_ids)
    else:
        false_flag_rate = 0.0

    if defect_ids:
        missed = sum(
            1 for cid in defect_ids if verdicts_by_claim_id[cid] == VERDICT_SUPPORTED
        )
        missed_defect_rate = missed / len(defect_ids)
    else:
        missed_defect_rate = 0.0

    return {
        "false_flag_rate": false_flag_rate,
        "missed_defect_rate": missed_defect_rate,
        "n_supported_labelled": len(supported_ids),
        "n_defect_labelled": len(defect_ids),
    }
