"""Unit tests for tracelearn_features/cpg_source.py."""

from tracelearn_features.cpg_source import extract_cpg_source


def test_empty_source_returns_empty_dict():
    assert extract_cpg_source("") == {}
    assert extract_cpg_source("   ") == {}
    assert extract_cpg_source(None) == {}  # type: ignore[arg-type]


def test_function_count():
    src = "int f(int x) { return x; }\nvoid g() { }"
    out = extract_cpg_source(src)
    assert out["function_count"] == 2


def test_loop_count():
    src = "void f() { for(int i=0;i<n;i++){} while(x>0){x--;} }"
    out = extract_cpg_source(src)
    assert out["loop_count"] == 2


def test_assign_in_condition_count():
    src = "void f(int* p) { if(x = *p++) {} while(y = next()) {} }"
    out = extract_cpg_source(src)
    assert out["assign_in_condition_count"] == 2


def test_comparison_count():
    src = "int f(int a, int b) { return a == b || a != b || a < b || a > b; }"
    out = extract_cpg_source(src)
    assert out["comparison_count"] >= 4


def test_decrement_in_loop_count():
    # i-- is in the for-header (not body), n-- is in the body — expect at least 1
    src = "void f(int n) { for(int i=n;i>0;i--){ n--; n--; } }"
    out = extract_cpg_source(src)
    assert out["decrement_in_loop_count"] >= 2


def test_unguarded_recursion_count():
    # Recursive with no base-case guard
    src = "int f(int n) { return n + f(n-1); }"
    out = extract_cpg_source(src)
    assert out["unguarded_recursion_count"] >= 1


def test_guarded_recursion_not_counted_as_unguarded():
    src = "int fib(int n) { if(n <= 1) return n; return fib(n-1) + fib(n-2); }"
    out = extract_cpg_source(src)
    assert out["unguarded_recursion_count"] == 0


def test_comments_and_strings_stripped():
    src = '// if(x = 1) -- loop\nvoid f() { /* for(;;) */ int x = 0; }'
    out = extract_cpg_source(src)
    assert out["assign_in_condition_count"] == 0
    assert out["loop_count"] == 0
    assert out["decrement_in_loop_count"] == 0


def test_returns_only_fillable_keys():
    out = extract_cpg_source("int main() { return 0; }")
    # Only source-computable keys are returned; graph-structural ones are absent
    graph_only = {"node_count", "edge_count", "max_depth",
                  "ast_ref_similarity", "array_write_oob_count",
                  "use_before_init_count", "loop_cond_var_unassigned_count",
                  "assign_feeds_output_count"}
    assert not graph_only.intersection(out.keys())
    assert "function_count" in out
    assert "comparison_count" in out
