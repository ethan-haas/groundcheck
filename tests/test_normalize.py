from groundcheck.normalize import extract_numbers, normalize


def test_normalize_collapses_whitespace_and_linewrap():
    a = "revenue   grew\n12%   in   fiscal 2023"
    b = "revenue grew\n\n  12% in fiscal\n2023"
    assert normalize(a) == normalize(b)


def test_normalize_unifies_curly_quotes_and_dashes():
    a = normalize('the CEO said “growth continued” — modestly')
    b = normalize("the CEO said \"growth continued\" - modestly")
    assert a == b


def test_normalize_is_case_insensitive():
    assert normalize("Revenue Grew 12%") == normalize("revenue grew 12%")


def test_normalize_trims_edge_punctuation_but_not_interior():
    assert normalize("Headcount rose to 512 employees.") == normalize("Headcount rose to 512 employees")
    # interior punctuation (a comma inside the sentence) is preserved
    assert normalize("revenue grew, modestly") != normalize("revenue grew modestly")


def test_normalize_empty_and_none():
    assert normalize("") == ""
    assert normalize(None) == ""


def test_normalize_is_pure_function_no_hidden_state():
    # two independent calls with the same input always agree -- this is
    # the property determinism-across-processes ultimately rests on.
    s = "Revenue grew 12%\nin fiscal 2023."
    assert normalize(s) == normalize(s)


def test_extract_numbers_strips_commas_and_currency():
    assert extract_numbers("The board approved $1,250,000 for automation.") == frozenset({"1250000"})


def test_extract_numbers_keeps_percent_sign_distinct_from_bare_number():
    nums = extract_numbers("revenue grew 12%, headcount grew by 12")
    assert "12%" in nums
    assert "12" in nums
    assert nums == frozenset({"12%", "12"})


def test_extract_numbers_multiple_and_decimals():
    nums = extract_numbers("churn fell to 3.2% from 4.5% with 512 employees")
    assert nums == frozenset({"3.2%", "4.5%", "512"})


def test_extract_numbers_none_found():
    assert extract_numbers("no digits here at all") == frozenset()


def test_extract_numbers_none_input():
    assert extract_numbers(None) == frozenset()
