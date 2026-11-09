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
