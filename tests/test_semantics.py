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
    out = extract_semantics("int main() { return 0; }")
    assert set(out) == {
        "assign_in_cond", "recursion", "increment", "decrement",
        "idx_minus1", "idx_plus1", "if_gt", "if_ge", "if_lt", "if_le",
        "loop_lt", "loop_le", "init_zero", "return_minus1", "base_case",
    }
    assert all(isinstance(v, int) for v in out.values())


@pytest.mark.parametrize("field", ["assign_in_cond", "recursion", "base_case"])
def test_binary_fields_are_zero_or_one(field: str):
    out = extract_semantics("int f(int n) { if (n == 0) return 0; return f(n - 1); }")
    assert out[field] in (0, 1)
