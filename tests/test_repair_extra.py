"""The second set of inverse edits: each produces the fix for the real student mistake it was written for."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from codestream_static import parse  # noqa: E402
from repair_extra import (  # noqa: E402
    extra_array_bounds,
    extra_off_by_one,
    extra_range_check,
    extra_stale_exit,
    extra_uninitialized,
)


def squash(code: str) -> str:
    return re.sub(r"\s+", "", code)


def fixed(repairs, op: str) -> list[str]:
    return [squash(r.code) for r in repairs if r.op == op]


def test_every_chained_compare_is_split_together():
    src = 'int main(){char ch;if(65<=ch<=90){}else if(97<=ch<=122){} return 0;}'
    got = fixed(extra_range_check(parse(src)), "chained_compare_split_all")
    assert got and "65<=ch&&ch<=90" in got[0] and "97<=ch&&ch<=122" in got[0]


def test_chained_compare_with_char_literals():
    src = "int main(){char c;if('a'<=c<='z'){} return 0;}"
    got = fixed(extra_range_check(parse(src)), "chained_compare_split_all")
    assert got and "'a'<=c&&c<='z'" in got[0]


def test_backwards_range_is_reversed():
    src = "int main(){int c;if(c <= 97 && c >= 122){} return 0;}"
    got = fixed(extra_range_check(parse(src)), "if_reverse_all_comparisons")
    assert got and "c>=97&&c<=122" in got[0]


def test_and_or_swap():
    got = fixed(extra_range_check(parse("int main(){int a;if(a<1 && a>5){} return 0;}")), "if_swap_and_or")
    assert got and "a<1||a>5" in got[0]


def test_comparison_without_a_literal_can_flip():
    ops = {r.op for r in extra_range_check(parse("int main(){int a,b;if(a<b){} return 0;}"))}
    assert "if_any_cmp_<_to_<=" in ops and "if_any_cmp_<_to_>" in ops


def test_variable_length_and_heap_arrays_are_enlarged():
    src = "int main(){int n; int a[n]; int *p = new int[n]; int *q = (int*)malloc(n); return 0;}"
    repairs = extra_array_bounds(parse(src))
    assert any("inta[(n)+1000]" in squash(r.code) for r in repairs)
    assert any("newint[(n)+1000]" in squash(r.code) for r in repairs)
    assert any("malloc((n)+8000)" in squash(r.code) for r in repairs)


def test_every_array_is_enlarged_at_once():
    got = fixed(extra_array_bounds(parse("int main(){int a[10]; int b[20]; return 0;}")), "enlarge_every_array")
    assert got and "a[1010]" in got[0] and "b[1020]" in got[0]


def test_a_stack_array_is_not_enlarged_past_the_stack_limit():
    got = fixed(extra_array_bounds(parse("int main(){int a[10000000]; int b[20]; int c[30]; return 0;}")), "enlarge_every_array")
    assert got and "a[10000000]" in got[0] and "b[1020]" in got[0]


def test_local_arrays_and_all_scalars_can_be_zeroed():
    repairs = extra_uninitialized(parse("int main(){int a[10]; int x, y; return x+y+a[0];}"))
    assert any("inta[10]={0};" in squash(r.code) for r in repairs)
    assert any("intx=0,y=0;" in squash(r.code) for r in repairs if r.op == "init_every_scalar_0")


def test_printed_value_edits():
    repairs = extra_off_by_one(parse('#include <stdio.h>\nint main(){int c=0; printf("%d\\n", c-1); return 0;}'))
    assert any('"%d\\n",c);' in squash(r.code) for r in repairs if r.op == "output_-1_removed")
    repairs = extra_off_by_one(parse("int main(){int c=0; cout << c << endl; return 0;}"))
    assert any("cout<<c+1<<endl" in squash(r.code) for r in repairs)
    assert not any("endl+1" in squash(r.code) for r in repairs)


def test_returned_value_edit_removes_exactly_the_offset():
    repairs = extra_off_by_one(parse("int f(int n){return n+1;} int main(){return f(1);}"))
    assert any("returnn;}" in squash(r.code) for r in repairs if r.op == "return_+1_removed")


def test_loop_headers_are_left_to_the_first_set():
    repairs = extra_off_by_one(parse("int main(){for(int i=0;i<n-1;i++){} return 0;}"))
    assert not [r for r in repairs if r.op.startswith(("formula_", "start_"))]


def test_for_loop_testing_the_wrong_variable():
    src = "int main(){int n=3;for(int i=0;i<n;i++){for(int j=0;i<n;j++){}} return 0;}"
    got = fixed(extra_stale_exit(parse(src)), "for_test_the_stepped_variable")
    assert got and "for(intj=0;j<n;j++)" in got[0]


def test_list_walk_that_never_advances_gets_a_braced_update():
    src = "int main(){Node* t = h; while(t != NULL) cout << t->data; return 0;}"
    got = [squash(r.code) for r in extra_stale_exit(parse(src)) if r.after == "t = t->next;"]
    assert got and "while(t!=NULL){cout<<t->data;t=t->next;}" in got[0]


def test_counter_loop_gets_an_update_inside_its_braces():
    src = "int main(){int i=0,n=3; while(i<n){ cout << i; } return 0;}"
    got = [squash(r.code) for r in extra_stale_exit(parse(src))]
    assert any("{cout<<i;i++;}" in g for g in got)


def test_narrow_ops_match_the_backend_list():
    sys.path.insert(0, str(ROOT))
    from repair_extra import NARROW_OPS

    from backend.app.diagnosis.xgb_classifier import NARROW_REPAIR_OPS

    assert NARROW_OPS == NARROW_REPAIR_OPS


def test_narrow_candidates_keep_only_the_precise_edits():
    from repair_extra import NARROW_OPS, narrow_candidates

    code = """#include <stdio.h>
int main(){ float b; int a[5]; int c[5]; scanf("%f", &b);
  if (18.5 <= b < 25) printf("Normal"); else if (b > 30) printf("Obese");
  return 0; }
"""
    got = narrow_candidates(parse(code))
    assert set(got) == set(NARROW_OPS)
    for cls, repairs in got.items():
        assert all(r.op in NARROW_OPS[cls] for r in repairs)
    assert [r.op for r in got["CPP_RANGE_CHECK"]] == ["chained_compare_split_all"]
    assert "18.5 <= b && b < 25" in got["CPP_RANGE_CHECK"][0].code
    assert [r.op for r in got["CPP_ARRAY_BOUNDS"]] == ["enlarge_every_array"]


def test_missing_for_step_is_put_back():
    code = "int main(){ int n = 5, s = 0; for (int i = 0; i < n; ) { s += i; } return s; }"
    got = [r for r in extra_stale_exit(parse(code)) if r.op == "for_add_missing_step"]
    assert [squash(r.code) for r in got] == [squash(code.replace("i < n; )", "i < n;i++)")),
                                            squash(code.replace("i < n; )", "i < n;i--)"))]


def test_for_loop_that_steps_in_its_body_is_left_alone():
    for body in ("i++;", "i += 2;", "i = i + 1;", "++i;"):
        code = "int main(){ int n = 5; for (int i = 0; i < n; ) { " + body + " } return 0; }"
        assert not [r for r in extra_stale_exit(parse(code)) if r.op == "for_add_missing_step"], body


def test_range_test_with_the_wrong_joiner_is_swapped():
    code = "int main(){ int x = 3; if (x >= 1 || x <= 10) return 1; return 0; }"
    got = [r for r in extra_range_check(parse(code)) if r.op == "range_test_swap_and_or"]
    assert len(got) == 1 and "x >= 1 && x <= 10" in got[0].code
    code = "int main(){ int s = 3; if (s < 0 && s > 100) return 1; return 0; }"
    got = [r for r in extra_range_check(parse(code)) if r.op == "range_test_swap_and_or"]
    assert len(got) == 1 and "s < 0 || s > 100" in got[0].code


def test_conditions_that_are_not_a_two_sided_range_are_not_swapped():
    for cond in ("x > 3 && n > 2", "x > 1 && x > 5", "a == 0 && b == 0", "x >= 1 && y <= 10"):
        code = "int main(){ int x = 1, y = 2, n = 3, a = 0, b = 0; if (" + cond + ") return 1; return 0; }"
        assert not [r for r in extra_range_check(parse(code)) if r.op == "range_test_swap_and_or"], cond


def test_bank_operators_do_not_take_a_call_for_a_loop():
    import pytest

    pytest.importorskip("fcntl")  # the generator imports the Linux-only sandbox runner
    from build_bank_synthetic import OPERATORS, label_possible

    code = "int cost_for(int w) { if (w <= 0) { return -1; } if (w <= 500) { return 5; } return 10; }\nint main() { return cost_for(3); }\n"
    assert OPERATORS["CPP_LOOP_BOUNDARY"](code) == []
    assert OPERATORS["CPP_STALE_EXIT"](code) == []
    assert not label_possible("CPP_LOOP_BOUNDARY", code) and label_possible("CPP_RANGE_CHECK", code)
    loop = "int main() { int s = 0; for (int i = 0; i < 5; i++) { s += i; } return s; }"
    assert [m[2] for m in OPERATORS["CPP_LOOP_BOUNDARY"](loop)] == ["i <= 5"]


def test_upward_loop_is_turned_downward():
    from repair_extra import extra_wrong_loop_dir

    code = "int main(){ int n = 3; for (int i = 0; i < n; i++) { n += 0; } return 0; }"
    got = extra_wrong_loop_dir(parse(code))
    assert [r.op for r in got] == ["for_run_downward"]
    assert "for (int i = (n) - 1; i >= 0; i--)" in got[0].code
    # an unsigned counter would never end; a loop that does not start at 0 is not this pattern
    assert extra_wrong_loop_dir(parse("int main(){ for (size_t i = 0; i < 5; i++) {} return 0; }")) == []
    assert extra_wrong_loop_dir(parse("int main(){ for (int i = 1; i < 5; i++) {} return 0; }")) == []
