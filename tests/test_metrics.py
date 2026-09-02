import pytest

from groundcheck import verify
from groundcheck.metrics import two_sided_score


def test_two_sided_score_perfect_checker_scores_zero_both_sides():
    verdicts = {"a": "supported", "b": "supported", "c": "unresolvable", "d": "span-mismatch"}
    result = two_sided_score(verdicts, expected_supported_claim_ids=["a", "b"], expected_defect_claim_ids=["c", "d"])
    assert result["false_flag_rate"] == 0.0
    assert result["missed_defect_rate"] == 0.0


def test_two_sided_score_flag_everything_checker_scores_useless():
    # a checker that flags every claim as broken: 0 missed defects, but
    # 100% false-flag rate on the genuinely clean claims -- proving a
    # blended accuracy alone would hide this failure mode.
    verdicts = {"a": "unresolvable", "b": "unresolvable", "c": "unresolvable", "d": "unresolvable"}
    result = two_sided_score(verdicts, expected_supported_claim_ids=["a", "b"], expected_defect_claim_ids=["c", "d"])
    assert result["false_flag_rate"] == 1.0
    assert result["missed_defect_rate"] == 0.0


def test_two_sided_score_never_flag_anything_checker_scores_useless_the_other_way():
    verdicts = {"a": "supported", "b": "supported", "c": "supported", "d": "supported"}
    result = two_sided_score(verdicts, expected_supported_claim_ids=["a", "b"], expected_defect_claim_ids=["c", "d"])
    assert result["false_flag_rate"] == 0.0
    assert result["missed_defect_rate"] == 1.0


def test_two_sided_score_rejects_overlapping_labels():
    with pytest.raises(ValueError):
        two_sided_score({"a": "supported"}, expected_supported_claim_ids=["a"], expected_defect_claim_ids=["a"])


def test_two_sided_score_rejects_missing_claim_id():
    with pytest.raises(ValueError):
        two_sided_score({"a": "supported"}, expected_supported_claim_ids=["a", "b"], expected_defect_claim_ids=[])


def test_two_sided_score_against_a_real_verify_call():
    sources = {"d": "The launch window opens at 09:00 and closes at 11:00."}
    citations = [
        {"claim_id": "ok", "text": "launch window opens at 09:00", "doc_id": "d", "quote": "launch window opens at 09:00"},
        {"claim_id": "bad-doc", "text": "x", "doc_id": "missing"},
        {"claim_id": "no-cite", "text": "x"},
    ]
    report = verify(answer="x", citations=citations, sources=sources)
    by_id = {cv.claim_id: cv.verdict for cv in report.claims}
    result = two_sided_score(by_id, expected_supported_claim_ids=["ok"], expected_defect_claim_ids=["bad-doc", "no-cite"])
    assert result["false_flag_rate"] == 0.0
    assert result["missed_defect_rate"] == 0.0
