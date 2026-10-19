"""CPG parser + feature extraction tests (master plan §9.3 R3, R-I6).

parse_cpg.py reads PROGpedia's shipped Code Property Graph — `*.dsc.csv` nodes
and `*.cpg.csv` AST/EOG/DFG edges (see `progpedia (1)/data.md`) — and computes
the `cpg` feature block the extractor consumes.

R3 milestone: >=95% parse rate on real data, matches data.md, failures logged
and dropped (never guessed). Structural features (counts, depth) are exact;
the four pg-rule detectors (assign-in-condition, unguarded recursion, array
OOB write, use-before-init) are conservative and each is one of the two
independent signals a pg conjunction requires — the compiler warning is the
other, so precision is protected by the conjunction, not the detector alone.
"""

from __future__ import annotations

import csv
from pathlib import Path

from scripts.parse_cpg import CPGGraph, cpg_features, parse_graph_text, parse_submission


def _graph(nodes: list[tuple[str, str, str]], edges: list[tuple[str, str, str]]) -> CPGGraph:
    """Build a CPGGraph from (id, type, token) nodes and (src, dst, type) edges."""
    g = CPGGraph()
    for nid, ntype, token in nodes:
        g.add_node(nid, ntype, token, "", "")
    for src, dst, etype in edges:
        g.add_edge(src, dst, etype, "", "")
    return g


# --------------------------------------------------------------- parsing


def test_parse_graph_text_reads_nodes_and_edges():
    dsc = "id,type,token,location,code\n1,TRANSLATIONUNITDECLARATION,,,\n2,FUNCTIONDECLARATION,main,,\n"
    cpg = "source_id,target_id,type,index,branch,name\n1,2,AST,,,\n"
    g = parse_graph_text(dsc, cpg)
    assert g.node_count == 2
    assert g.edge_count == 1
    assert g.nodes["2"].type == "FUNCTIONDECLARATION"
    assert g.nodes["2"].token == "main"


def test_parse_graph_text_tolerates_blank_and_malformed_lines():
    dsc = "id,type,token,location,code\n1,TRANSLATIONUNITDECLARATION,,,\n\nnotanumber,BAD,,,\n2,LITERAL,x,,\n"
    cpg = "source_id,target_id,type,index,branch,name\n1,2,AST,,,\n1,99,AST,,,\n"
    g = parse_graph_text(dsc, cpg)
    assert g.node_count == 2          # malformed node skipped
    assert g.edge_count == 1          # dangling edge (target 99) dropped, not guessed


def test_parse_submission_missing_files_returns_none(tmp_path: Path):
    assert parse_submission(tmp_path / "no.cpg.csv", tmp_path / "no.dsc.csv") is None


# ------------------------------------------------------ structural features


def test_structural_counts_and_depth():
    # 1 -> 2(func) -> 3(compound) -> 4(if) -> 5(binop)
    g = _graph(
        [("1", "TRANSLATIONUNITDECLARATION", ""), ("2", "FUNCTIONDECLARATION", "main"),
         ("3", "COMPOUNDSTATEMENT", ""), ("4", "IFSTATEMENT", ""), ("5", "BINARYOPERATOR", "<")],
        [("1", "2", "AST"), ("2", "3", "AST"), ("3", "4", "AST"), ("4", "5", "AST")],
    )
    f = cpg_features(g)
    assert f["available"] is True
    assert f["node_count"] == 5
    assert f["edge_count"] == 4
    assert f["function_count"] == 1
    assert f["max_depth"] == 5   # 1->2->3->4->5
    assert f["comparison_count"] == 1


def test_function_count_includes_methods_and_constructors():
    g = _graph(
        [("1", "FUNCTIONDECLARATION", "f"), ("2", "METHODDECLARATION", "m"),
         ("3", "CONSTRUCTORDECLARATION", "C")],
        [],
    )
    assert cpg_features(g)["function_count"] == 3


def test_loop_count_for_while_foreach_do():
    g = _graph(
        [("1", "FORSTATEMENT", ""), ("2", "WHILESTATEMENT", ""),
         ("3", "FOREACHSTATEMENT", ""), ("4", "DOSTATEMENT", "")],
        [],
    )
    assert cpg_features(g)["loop_count"] == 4


def test_comparison_count_only_comparison_operators():
    g = _graph(
        [("1", "BINARYOPERATOR", "<"), ("2", "BINARYOPERATOR", "=="),
         ("3", "BINARYOPERATOR", ">="), ("4", "BINARYOPERATOR", "+"),
         ("5", "BINARYOPERATOR", "="), ("6", "BINARYOPERATOR", "!=")],
        [],
    )
    assert cpg_features(g)["comparison_count"] == 4  # <, ==, >=, != (not + or =)


def test_empty_graph_features_are_available_and_zero():
    g = CPGGraph()
    f = cpg_features(g)
    assert f["available"] is True
    assert f["node_count"] == 0
    assert f["max_depth"] == 0


# ------------------------------------------------------- pg-2: unguarded recursion


def test_unguarded_recursion_detected():
    # main calls main, no base-case if inside main -> unguarded
    g = _graph(
        [("1", "FUNCTIONDECLARATION", "main"), ("2", "COMPOUNDSTATEMENT", ""),
         ("3", "CALLEXPRESSION", "main")],
        [("1", "2", "AST"), ("2", "3", "AST")],
    )
    assert cpg_features(g)["unguarded_recursion_count"] == 1


def test_recursion_with_base_case_is_guarded():
    # main calls main but has an if->return base case -> guarded, not counted
    g = _graph(
        [("1", "FUNCTIONDECLARATION", "main"), ("2", "COMPOUNDSTATEMENT", ""),
         ("3", "IFSTATEMENT", ""), ("4", "RETURNSTATEMENT", ""),
         ("5", "CALLEXPRESSION", "main")],
        [("1", "2", "AST"), ("2", "3", "AST"), ("3", "4", "AST"), ("2", "5", "AST")],
    )
    assert cpg_features(g)["unguarded_recursion_count"] == 0


def test_non_recursive_function_not_counted():
    g = _graph(
        [("1", "FUNCTIONDECLARATION", "main"), ("2", "COMPOUNDSTATEMENT", ""),
         ("3", "CALLEXPRESSION", "printf")],
        [("1", "2", "AST"), ("2", "3", "AST")],
    )
    assert cpg_features(g)["unguarded_recursion_count"] == 0


# --------------------------------------------------- pg-3: array OOB write


def test_array_write_beyond_literal_size_detected():
    # int a[3]; a[5] = x;  -> subscription index 5 >= declared size 3
    g = _graph(
        [("1", "VARIABLEDECLARATION", "a"), ("2", "ARRAYSUBSCRIPTIONEXPRESSION", ""),
         ("3", "LITERAL", "5"), ("4", "BINARYOPERATOR", "="), ("5", "DECLAREDREFERENCEEXPRESSION", "a")],
        [("2", "3", "AST"), ("4", "2", "AST"), ("2", "5", "AST")],
    )
    # mark declaration size via token annotation used by the parser
    g.nodes["1"].code = "a[3]"
    assert cpg_features(g)["array_write_oob_count"] == 1


def test_array_write_within_bounds_not_counted():
    g = _graph(
        [("1", "VARIABLEDECLARATION", "a"), ("2", "ARRAYSUBSCRIPTIONEXPRESSION", ""),
         ("3", "LITERAL", "2"), ("4", "BINARYOPERATOR", "="), ("5", "DECLAREDREFERENCEEXPRESSION", "a")],
        [("2", "3", "AST"), ("4", "2", "AST"), ("2", "5", "AST")],
    )
    g.nodes["1"].code = "a[3]"
    assert cpg_features(g)["array_write_oob_count"] == 0


# ------------------------------------------- pg-1: assign in condition


def test_assignment_in_if_condition_detected():
    # if (x = n - 1)  -> a '=' BINARYOPERATOR inside the if's condition subtree
    g = _graph(
        [("1", "IFSTATEMENT", ""), ("2", "BINARYOPERATOR", "="),
         ("3", "DECLAREDREFERENCEEXPRESSION", "x"), ("4", "BINARYOPERATOR", "-")],
        [("1", "2", "AST"), ("2", "3", "AST"), ("2", "4", "AST")],
    )
    assert cpg_features(g)["assign_in_condition_count"] == 1


def test_plain_if_condition_not_counted():
    # if (x < n) -> comparison, not assignment
    g = _graph(
        [("1", "IFSTATEMENT", ""), ("2", "BINARYOPERATOR", "<"),
         ("3", "DECLAREDREFERENCEEXPRESSION", "x")],
        [("1", "2", "AST"), ("2", "3", "AST")],
    )
    assert cpg_features(g)["assign_in_condition_count"] == 0


def test_assignment_in_loop_body_not_condition_not_counted():
    # for(...) { x = 1; } -> '=' in body, not condition
    g = _graph(
        [("1", "FORSTATEMENT", ""), ("2", "COMPOUNDSTATEMENT", ""),
         ("3", "BINARYOPERATOR", "="), ("4", "BINARYOPERATOR", "<")],
        [("1", "2", "AST"), ("2", "3", "AST"), ("1", "4", "AST")],
    )
    # condition child (4) is a comparison; the '=' (3) is inside the body compound
    assert cpg_features(g)["assign_in_condition_count"] == 0


# --------------------------------------------- pg-4: use before init


def test_use_before_init_detected():
    # declaration with no initializer, then a DFG use of the variable
    g = _graph(
        [("1", "VARIABLEDECLARATION", "x"), ("2", "UNINITIALIZEDVALUE", ""),
         ("3", "DECLAREDREFERENCEEXPRESSION", "x"), ("4", "BINARYOPERATOR", "<")],
        [("3", "4", "AST")],
    )
    g.nodes["1"].code = "x"          # no '= init'
    g.nodes["2"].code = ""           # explicit uninitialized marker
    assert cpg_features(g)["use_before_init_count"] >= 1


def test_initialized_variable_not_use_before_init():
    g = _graph(
        [("1", "VARIABLEDECLARATION", "x"), ("2", "LITERAL", "0"),
         ("3", "DECLAREDREFERENCEEXPRESSION", "x"), ("4", "BINARYOPERATOR", "<")],
        [("1", "2", "AST"), ("3", "4", "AST")],
    )
    g.nodes["1"].code = "x = 0"
    assert cpg_features(g)["use_before_init_count"] == 0


# ------------------------------------------------- decrement in loop (class-8 det)


def test_decrement_in_loop_detected():
    # for(...) { i--; } -> UNARYOPERATOR '--' inside a loop subtree
    g = _graph(
        [("1", "FORSTATEMENT", ""), ("2", "COMPOUNDSTATEMENT", ""),
         ("3", "UNARYOPERATOR", "--"), ("4", "DECLAREDREFERENCEEXPRESSION", "i")],
        [("1", "2", "AST"), ("2", "3", "AST"), ("3", "4", "AST")],
    )
    assert cpg_features(g)["decrement_in_loop_count"] == 1


def test_decrement_outside_loop_not_counted():
    g = _graph(
        [("1", "COMPOUNDSTATEMENT", ""), ("2", "UNARYOPERATOR", "--"),
         ("3", "DECLAREDREFERENCEEXPRESSION", "i")],
        [("1", "2", "AST"), ("2", "3", "AST")],
    )
    assert cpg_features(g)["decrement_in_loop_count"] == 0


# ------------------------------------- class-10 det: loop cond var unassigned


def test_loop_cond_var_unassigned_in_body_detected():
    # while (k != 0) { ... } with no assignment to k in the body
    g = _graph(
        [("1", "WHILESTATEMENT", ""), ("2", "BINARYOPERATOR", "!="),
         ("3", "DECLAREDREFERENCEEXPRESSION", "k"), ("4", "COMPOUNDSTATEMENT", ""),
         ("5", "DECLAREDREFERENCEEXPRESSION", "k")],
        [("1", "2", "AST"), ("2", "3", "AST"), ("1", "4", "AST"), ("4", "5", "AST")],
    )
    assert cpg_features(g)["loop_cond_var_unassigned_count"] == 1


def test_loop_cond_var_assigned_in_body_not_counted():
    g = _graph(
        [("1", "WHILESTATEMENT", ""), ("2", "BINARYOPERATOR", "!="),
         ("3", "DECLAREDREFERENCEEXPRESSION", "k"), ("4", "COMPOUNDSTATEMENT", ""),
         ("5", "BINARYOPERATOR", "="), ("6", "DECLAREDREFERENCEEXPRESSION", "k")],
        [("1", "2", "AST"), ("2", "3", "AST"), ("1", "4", "AST"), ("4", "5", "AST"), ("5", "6", "AST")],
    )
    assert cpg_features(g)["loop_cond_var_unassigned_count"] == 0


# -------------------------------------- refined pg-3: index safety analysis
#
# "array write beyond fixed declared size" = a write to a fixed-size array
# whose index is not statically bounded below the size. Ground-truthed on real
# RUNTIME_ERROR submissions: unbounded input-driven writes (`aux[i]=loc` in
# `for(i=0;loc!=0;i++)` on `int aux[30]`) are genuine OOB crashes, while
# `for(i=0;i<3;i++) a[i]=` on `int a[3]` is safe and must NOT fire. Measured
# yield: 96 single-firing rows on real data vs the plan's ~100 pg-3 expectation.


def _loop_graph(cond_type, cond_token, cond_literal, index_var="i"):
    # int a[3]; for (index_var=0; index_var <cond_token> cond_literal; ...) a[index_var] = 0;
    # subscription children order = [base ref, index ref] (matches real CPGs)
    return _graph(
        [("1", "VARIABLEDECLARATION", "a"),
         ("2", "FORSTATEMENT", ""), ("3", "BINARYOPERATOR", "="), ("4", "LITERAL", "0"),
         ("5", "BINARYOPERATOR", cond_token), ("6", "DECLAREDREFERENCEEXPRESSION", index_var),
         ("7", "LITERAL", cond_literal),
         ("8", "COMPOUNDSTATEMENT", ""), ("9", "ARRAYSUBSCRIPTIONEXPRESSION", ""),
         ("13", "DECLAREDREFERENCEEXPRESSION", "a"),
         ("10", "DECLAREDREFERENCEEXPRESSION", index_var),
         ("11", "BINARYOPERATOR", "="), ("12", "LITERAL", "0")],
        [("2", "3", "AST"), ("3", "6", "AST"), ("3", "4", "AST"),
         ("2", "5", "AST"), ("5", "6", "AST"), ("5", "7", "AST"),
         ("2", "8", "AST"), ("8", "11", "AST"), ("11", "9", "AST"),
         ("9", "13", "AST"), ("9", "10", "AST"), ("11", "12", "AST")],
    )


def test_array_write_safely_bounded_by_literal_lt_not_counted():
    # for (i=0; i<3; i++) a[i]=0;  on int a[3] -> max index 2, safe
    g = _loop_graph("BINARYOPERATOR", "<", "3")
    g.nodes["1"].code = "a[3]"
    assert cpg_features(g)["array_write_oob_count"] == 0


def test_array_write_le_bound_at_size_counted():
    # for (i=0; i<=3; i++) a[i]=0;  on int a[3] -> i=3 writes a[3], OOB
    g = _loop_graph("BINARYOPERATOR", "<=", "3")
    g.nodes["1"].code = "a[3]"
    assert cpg_features(g)["array_write_oob_count"] == 1


def test_array_write_le_bound_below_size_not_counted():
    # for (i=0; i<=2; i++) a[i]=0;  on int a[3] -> max index 2, safe
    g = _loop_graph("BINARYOPERATOR", "<=", "2")
    g.nodes["1"].code = "a[3]"
    assert cpg_features(g)["array_write_oob_count"] == 0


def test_array_write_variable_bound_counted():
    # for (i=0; i<n; i++) a[i]=0;  -> n unbounded relative to size 3
    g = _graph(
        [("1", "VARIABLEDECLARATION", "a"),
         ("2", "FORSTATEMENT", ""), ("3", "BINARYOPERATOR", "="), ("4", "LITERAL", "0"),
         ("5", "BINARYOPERATOR", "<"), ("6", "DECLAREDREFERENCEEXPRESSION", "i"),
         ("7", "DECLAREDREFERENCEEXPRESSION", "n"),
         ("8", "COMPOUNDSTATEMENT", ""), ("9", "ARRAYSUBSCRIPTIONEXPRESSION", ""),
         ("13", "DECLAREDREFERENCEEXPRESSION", "a"),
         ("10", "DECLAREDREFERENCEEXPRESSION", "i"),
         ("11", "BINARYOPERATOR", "="), ("12", "LITERAL", "0")],
        [("2", "3", "AST"), ("3", "6", "AST"), ("3", "4", "AST"),
         ("2", "5", "AST"), ("5", "6", "AST"), ("5", "7", "AST"),
         ("2", "8", "AST"), ("8", "11", "AST"), ("11", "9", "AST"),
         ("9", "13", "AST"), ("9", "10", "AST"), ("11", "12", "AST")],
    )
    g.nodes["1"].code = "a[3]"
    assert cpg_features(g)["array_write_oob_count"] == 1


def test_array_write_direct_variable_index_counted():
    # a[idx]=0;  with no enclosing loop at all -> idx comes from input, unsafe
    g = _graph(
        [("1", "VARIABLEDECLARATION", "a"), ("2", "ARRAYSUBSCRIPTIONEXPRESSION", ""),
         ("6", "DECLAREDREFERENCEEXPRESSION", "a"),
         ("3", "DECLAREDREFERENCEEXPRESSION", "idx"), ("4", "BINARYOPERATOR", "="),
         ("5", "LITERAL", "0")],
        [("4", "2", "AST"), ("2", "6", "AST"), ("2", "3", "AST"), ("4", "5", "AST")],
    )
    g.nodes["1"].code = "a[3]"
    assert cpg_features(g)["array_write_oob_count"] == 1


def test_array_write_increment_index_in_unbounded_loop_counted():
    # for (i=0; loc!=0; i++) aux[i++]=loc;  on int aux[30] -> unbounded input loop
    g = _graph(
        [("1", "VARIABLEDECLARATION", "aux"),
         ("2", "FORSTATEMENT", ""), ("3", "BINARYOPERATOR", "="), ("4", "LITERAL", "0"),
         ("5", "BINARYOPERATOR", "!="), ("6", "DECLAREDREFERENCEEXPRESSION", "loc"),
         ("7", "COMPOUNDSTATEMENT", ""),
         ("8", "ARRAYSUBSCRIPTIONEXPRESSION", ""), ("13", "DECLAREDREFERENCEEXPRESSION", "aux"),
         ("9", "UNARYOPERATOR", "++"),
         ("10", "DECLAREDREFERENCEEXPRESSION", "i"),
         ("11", "BINARYOPERATOR", "="), ("12", "DECLAREDREFERENCEEXPRESSION", "loc")],
        [("2", "3", "AST"), ("3", "10", "AST"), ("3", "4", "AST"),
         ("2", "5", "AST"), ("5", "6", "AST"),
         ("2", "7", "AST"), ("7", "11", "AST"), ("11", "8", "AST"),
         ("8", "13", "AST"), ("8", "9", "AST"), ("9", "10", "AST"), ("11", "12", "AST")],
    )
    g.nodes["1"].code = "aux[30]"
    assert cpg_features(g)["array_write_oob_count"] == 1


def test_array_write_literal_index_in_code_when_token_empty():
    # Real data: 20% of LITERAL nodes carry the value in `code` with empty token.
    g = _graph(
        [("1", "VARIABLEDECLARATION", "a"), ("2", "ARRAYSUBSCRIPTIONEXPRESSION", ""),
         ("6", "DECLAREDREFERENCEEXPRESSION", "a"),
         ("3", "LITERAL", ""), ("4", "BINARYOPERATOR", "="), ("5", "DECLAREDREFERENCEEXPRESSION", "x")],
        [("2", "6", "AST"), ("2", "3", "AST"), ("4", "2", "AST"), ("4", "5", "AST")],
    )
    g.nodes["1"].code = "a[3]"
    g.nodes["3"].code = "5"     # token empty, value only in code
    assert cpg_features(g)["array_write_oob_count"] == 1


def test_complex_index_expression_is_skipped_not_guessed():
    # a[f(x)] = 0 -> index is a call; cannot decide statically, never guess
    g = _graph(
        [("1", "VARIABLEDECLARATION", "a"), ("2", "ARRAYSUBSCRIPTIONEXPRESSION", ""),
         ("6", "DECLAREDREFERENCEEXPRESSION", "a"),
         ("3", "CALLEXPRESSION", "f"), ("4", "BINARYOPERATOR", "="),
         ("5", "DECLAREDREFERENCEEXPRESSION", "x")],
        [("2", "6", "AST"), ("2", "3", "AST"), ("4", "2", "AST"), ("3", "5", "AST")],
    )
    g.nodes["1"].code = "a[3]"
    assert cpg_features(g)["array_write_oob_count"] == 0


def test_array_write_to_macro_sized_array_resolves_via_define(tmp_path: Path):
    # int v[MAX]; v[5]=x; with #define MAX 3 in the sibling source file
    dsc = ("id,type,token,location,code\n"
           "1,VARIABLEDECLARATION,v,,v[MAX]\n"
           "2,ARRAYSUBSCRIPTIONEXPRESSION,,,\n"
           "3,LITERAL,5,,\n"
           "4,BINARYOPERATOR,=,,\n"
           "5,DECLAREDREFERENCEEXPRESSION,x,,\n"
           "6,DECLAREDREFERENCEEXPRESSION,v,,\n")
    cpg = ("source_id,target_id,type,index,branch,name\n"
           "4,2,AST,,,\n"
           "2,3,AST,,,\n"
           "2,6,AST,,,\n"
           "4,5,AST,,,\n")
    (tmp_path / "v.c").write_text("#define MAX 3\nint v[MAX];\nint main(){ v[5]=1; }\n", encoding="utf-8")
    (tmp_path / "v_c.cpg.csv").write_text(cpg, encoding="utf-8")
    (tmp_path / "v_c.dsc.csv").write_text(dsc, encoding="utf-8")
    g = parse_submission(tmp_path / "v_c.cpg.csv", tmp_path / "v_c.dsc.csv")
    assert g is not None
    assert cpg_features(g)["array_write_oob_count"] == 1


# ------------------------------------- refined pg-2: both guard patterns
#
# Ground truth: the naive "if->return only" guard flagged every tree traversal
# (`for(child) walk(child);`) as missing-base-case. A recursion is guarded when
# (a) an if->return base case exists, OR (b) the self-call is itself nested
# under a conditional/loop. Only truly unguarded recursion always crashes, so
# the RUNTIME_ERROR conjunction stays coherent.


def test_call_nested_in_if_without_return_is_guarded():
    # void f(n) { if (n > 0) f(n-1); }  -> terminates at n<=0, NOT missing base
    g = _graph(
        [("1", "FUNCTIONDECLARATION", "f"), ("2", "COMPOUNDSTATEMENT", ""),
         ("3", "IFSTATEMENT", ""), ("4", "BINARYOPERATOR", ">"),
         ("5", "DECLAREDREFERENCEEXPRESSION", "n"), ("6", "LITERAL", "0"),
         ("7", "CALLEXPRESSION", "f")],
        [("1", "2", "AST"), ("2", "3", "AST"), ("3", "4", "AST"), ("4", "5", "AST"),
         ("4", "6", "AST"), ("3", "7", "AST")],
    )
    assert cpg_features(g)["unguarded_recursion_count"] == 0


def test_call_in_loop_is_guarded():
    # for (child ...) walk(child);  -> bounded by the loop, NOT missing base
    g = _graph(
        [("1", "FUNCTIONDECLARATION", "walk"), ("2", "COMPOUNDSTATEMENT", ""),
         ("3", "FOREACHSTATEMENT", ""), ("4", "CALLEXPRESSION", "walk"),
         ("5", "DECLAREDREFERENCEEXPRESSION", "child")],
        [("1", "2", "AST"), ("2", "3", "AST"), ("3", "4", "AST"), ("3", "5", "AST")],
    )
    assert cpg_features(g)["unguarded_recursion_count"] == 0


def test_top_level_self_call_with_nonreturning_if_is_unguarded():
    # f(n) { if (debug) print(); f(n-1); } -> the if never stops recursion
    g = _graph(
        [("1", "FUNCTIONDECLARATION", "f"), ("2", "COMPOUNDSTATEMENT", ""),
         ("3", "IFSTATEMENT", ""), ("4", "CALLEXPRESSION", "print"),
         ("5", "CALLEXPRESSION", "f")],
        [("1", "2", "AST"), ("2", "3", "AST"), ("3", "4", "AST"), ("2", "5", "AST")],
    )
    assert cpg_features(g)["unguarded_recursion_count"] == 1


# ------------------------------------------- self-call receiver correctness
#
# Ground truth on all 4,906 real submissions: of 251 same-name member calls
# inside same-name functions, 79 target a DIFFERENT object's method
# (`self.vertexes.append` inside `def append`, `self.vertList.has_key` inside
# `def has_key`) — every one of the 5 measured false pg-2 flags was this shape.
# Only a bare call or a member call with receiver exactly self/this/super can
# target the function itself; unknown receivers are never guessed (R3).


def test_member_call_on_other_object_is_not_recursion():
    # def append(self, v): self.vertexes.append(v)  -> calls list.append, not itself
    g = _graph(
        [("1", "METHODDECLARATION", "append"), ("2", "COMPOUNDSTATEMENT", ""),
         ("3", "MEMBERCALLEXPRESSION", "append")],
        [("1", "2", "AST"), ("2", "3", "AST")],
    )
    g.nodes["3"].code = "self.vertexes.append(vertex)"
    assert cpg_features(g)["unguarded_recursion_count"] == 0


def test_member_call_with_self_receiver_is_recursion():
    # def walk(self, n): self.walk(n)  -> genuine same-method recursion
    g = _graph(
        [("1", "METHODDECLARATION", "walk"), ("2", "COMPOUNDSTATEMENT", ""),
         ("3", "MEMBERCALLEXPRESSION", "walk")],
        [("1", "2", "AST"), ("2", "3", "AST")],
    )
    g.nodes["3"].code = "self.walk(child)"
    assert cpg_features(g)["unguarded_recursion_count"] == 1


def test_member_call_with_unknown_receiver_never_counted():
    # receiver not readable from `code` -> cannot decide -> never guess (R3)
    g = _graph(
        [("1", "METHODDECLARATION", "f"), ("2", "COMPOUNDSTATEMENT", ""),
         ("3", "MEMBERCALLEXPRESSION", "f")],
        [("1", "2", "AST"), ("2", "3", "AST")],
    )
    g.nodes["3"].code = ""
    assert cpg_features(g)["unguarded_recursion_count"] == 0


# ------------------------------------------------------- real-data parse rate


def _real_submissions(limit: int = 400):
    root = Path(r"G:\TraceLearn\Datasets_RAW\progpedia")
    if not root.is_dir():
        return []
    out = []
    for pdir in sorted(root.iterdir()):
        if not pdir.is_dir():
            continue
        for dsc in pdir.rglob("*.dsc.csv"):
            cpg = dsc.with_name(dsc.name.replace(".dsc.csv", ".cpg.csv"))
            out.append((cpg, dsc))
            if len(out) >= limit:
                return out
    return out


def test_real_data_parse_rate_at_least_95_percent():
    subs = _real_submissions()
    if not subs:
        import pytest
        pytest.skip("PROGpedia raw data not present")
    parsed = failures = 0
    for cpg, dsc in subs:
        graph = parse_submission(cpg, dsc)
        if graph is None:
            failures += 1
        else:
            parsed += 1
            feats = cpg_features(graph)
            assert feats["available"] is True
            assert feats["node_count"] >= 0
    total = parsed + failures
    rate = parsed / total if total else 0.0
    assert rate >= 0.95, f"parse rate {rate:.2%} below 95% ({failures} failures / {total})"
