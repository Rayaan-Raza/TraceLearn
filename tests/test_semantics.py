"""Source-semantics feature tests.

These features are deterministic source-code signals (never label metadata).
They are computed for SYNTHETIC and CODESTREAM rows by the merge normalizer.
"""

from __future__ import annotations

import pytest

from tracelearn_features.semantics import extract_semantics


def test_detects_assignment_in_condition():
    out = extract_semantics(
        "int main() { int x = 0; if (x = 1) { x++; } while (x = 2) { x--; } }"
    )
    assert out["assign_in_cond"] == 1


def test_detects_recursion_and_base_case():
    out = extract_semantics(
        "int f(int n) { if (n <= 1) return 1; return n * f(n - 1); }"
    )
    assert out["recursion"] == 1
    assert out["base_case"] == 1


def test_detects_index_and_loop_comparison_patterns():
    out = extract_semantics(
        "int main() { int a[10]; for (int i = 0; i <= 9; i++) "
        "a[i - 1] = a[i + 1]; return a[0]; }"
    )
    assert out["loop_le"] == 1
    assert out["loop_lt"] == 0
    assert out["idx_minus1"] == 1
    assert out["idx_plus1"] == 1
    assert out["increment"] == 1


def test_detects_decrement_zero_init_and_return_minus_one():
    out = extract_semantics(
        "int main() { int s = 0; for (int i = 10; i > 0; i--) { s += i; } "
        "return s - 1; }"
    )
    assert out["decrement"] == 1
    assert out["init_zero"] == 1
    assert out["return_minus1"] == 1


def test_strips_comments_and_strings_before_counting():
    out = extract_semantics(
        '// if (x = 1) ++ --\n'
        'int main() { const char *s = "++ -- a[i-1]"; return 0; }'
    )
    assert out["assign_in_cond"] == 0
    assert out["increment"] == 0
    assert out["decrement"] == 0
    assert out["idx_minus1"] == 0


def test_empty_source_returns_empty_mapping():
    assert extract_semantics("") == {}
    assert extract_semantics("   \n\t") == {}


def test_all_registry_semantics_fields_are_present():
    from tracelearn_features.schema import FEATURE_BLOCKS

    out = extract_semantics("int main() { return 0; }")
    assert set(out) == set(FEATURE_BLOCKS["semantics"])
    assert all(isinstance(v, int) for v in out.values())


@pytest.mark.parametrize("field", ["assign_in_cond", "recursion", "base_case"])
def test_binary_fields_are_zero_or_one(field: str):
    out = extract_semantics("int f(int n) { if (n == 0) return 0; return f(n - 1); }")
    assert out[field] in (0, 1)


# ------------------------------------------------ surface patterns (real-code bugs)

PATTERN_CASES = [
    ("chained_compare", "int main(){int ch; if (65<=ch<=90) {} }", "int main(){int ch; if (65<=ch && ch<=90) {} }"),
    ("index_is_bound", "int main(){int n; int a[5]; return a[n];}", "int main(){int n; int a[n]; return a[0];}"),
    ("scanf_no_amp", 'int main(){int n; scanf("%d", n);}', 'int main(){int n; scanf("%d", &n);}'),
    ("no_input_read", 'int main(){printf("49");}', 'int main(){int n; scanf("%d", &n);}'),
    ("prompt_text", 'int main(){printf("Enter a number: ");}', 'int main(){printf("Tax: ");}'),
    ("printf_addr_arg", 'int main(){char c; printf("%c", &c);}', 'int main(){char c; printf("%c", c);}'),
    ("int_div_literals", "int main(){double d = 1/2; }", "int main(){int n; double d = n/2; }"),
    ("char_vs_string_cmp", 'int main(){char c; if (c >= "A") {} }', "int main(){char c; if (c >= 'A') {} }"),
    ("empty_body_stmt", "int main(){int i; for (i=0;i<3;i++); }", "int main(){int i; for (i=0;i<3;i++) {} }"),
    ("loop_var_reused", "int main(){int i; for (i=0;i<3;i++){ for (i=0;i<2;i++){} } }",
     "int main(){int i,j; for (i=0;i<3;i++){ for (j=0;j<2;j++){} } }"),
]


@pytest.mark.parametrize("feature,buggy,clean", PATTERN_CASES, ids=[c[0] for c in PATTERN_CASES])
def test_surface_pattern_fires_on_the_bug_and_not_on_the_fix(feature, buggy, clean):
    assert extract_semantics(buggy)[feature] >= 1
    assert extract_semantics(clean)[feature] == 0


def test_templates_and_do_while_are_not_mistaken_for_bugs():
    out = extract_semantics(
        "#include <vector>\nint main(){ std::vector<int> v; int x; std::cin >> x; "
        "do { x--; } while (x > 0); if (x < 3 && x > 1) {} }"
    )
    assert out["chained_compare"] == 0
    assert out["empty_body_stmt"] == 0


def test_array_declaration_with_the_length_is_not_an_index_read():
    assert extract_semantics("int main(){int n; int a[n]; vector<int> v(n);}")["index_is_bound"] == 0


def test_scanf_into_a_string_without_ampersand_is_fine():
    assert extract_semantics('int main(){char s[10]; scanf("%s", s);}')["scanf_no_amp"] == 0


def test_comments_do_not_trigger_patterns():
    out = extract_semantics("int main(){ int n; /* if (1<=n<=3) */ // scanf(\"%d\", n);\n return 0; }")
    assert out["chained_compare"] == 0 and out["scanf_no_amp"] == 0


def test_plus1_index_in_a_loop_that_runs_to_n_is_flagged_but_n_minus_1_is_fine():
    bug = "int main(){int n; int a[9]; for (int i = 0; i < n; i++) { if (a[i] < a[i + 1]) {} } }"
    ok = "int main(){int n; int a[9]; for (int i = 0; i < n - 1; i++) { if (a[i] < a[i + 1]) {} } }"
    assert extract_semantics(bug)["plus1_index_in_full_loop"] == 1
    assert extract_semantics(ok)["plus1_index_in_full_loop"] == 0
    while_bug = "int main(){int n,i=0; int a[9]; while (i < n) { if (a[i] > a[i+1]) {} i++; } }"
    assert extract_semantics(while_bug)["plus1_index_in_full_loop"] == 1


def test_minus1_index_in_a_loop_that_starts_at_zero_is_flagged_but_start_at_one_is_fine():
    bug = "int main(){int n; int a[9]; for (int i = 0; i < n; i++) { if (a[i] < a[i - 1]) {} } }"
    ok = "int main(){int n; int a[9]; for (int i = 1; i < n; i++) { if (a[i] < a[i - 1]) {} } }"
    assert extract_semantics(bug)["minus1_index_from_zero"] == 1
    assert extract_semantics(ok)["minus1_index_from_zero"] == 0
