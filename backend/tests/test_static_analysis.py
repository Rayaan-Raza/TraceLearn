from backend.app.analysis.static_analyzer import StaticAnalyzer

def test_range_plus_one_static_pattern():
    code = """def sum_first_n(n):
    s=0
    for i in range(n+1):
        s+=i
    return s
"""
    items = StaticAnalyzer().analyze(code, "sum_first_n")
    codes = {i.evidence_code for i in items}
    assert "STATIC_RANGE_N_PLUS_ONE" in codes

def test_value_used_as_index_pattern():
    code = """def first_negative(nums):
    for x in nums:
        if nums[x] < 0:
            return nums[x]
    return None
"""
    items = StaticAnalyzer().analyze(code, "first_negative")
    assert any(i.evidence_code == "STATIC_ITER_VALUE_USED_AS_INDEX" for i in items)

def test_missing_return_pattern():
    code = """def square_number(x):
    print(x*x)
"""
    items = StaticAnalyzer().analyze(code, "square_number")
    codes = {i.evidence_code for i in items}
    assert "STATIC_PRINT_INSTEAD_OF_RETURN" in codes or "STATIC_NO_RETURN" in codes
