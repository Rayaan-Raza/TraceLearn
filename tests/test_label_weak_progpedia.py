"""TDD for scripts/label_weak_progpedia.py (Task 7: pg-1..pg-4 -> tier1b rows).

Every fixture is synthetic (tmp_path); real-data yield is verified by the CLI
run + verify_dataset afterwards. Row shape follows plan §3.2 and must pass
verify_dataset.check_row (G1) untouched.
"""

import csv
import json

from scripts.label_weak_progpedia import fire_rules, label_rows
from scripts.verify_dataset import check_row

# --------------------------------------------------------------- CPG fixtures


def _dsc_cpg(nodes, edges):
    dsc_buf = __import__("io").StringIO()
    w = csv.writer(dsc_buf)
    w.writerow(["id", "type", "token", "location", "code"])
    w.writerows(nodes)
    cpg_buf = __import__("io").StringIO()
    w2 = csv.writer(cpg_buf)
    w2.writerow(["source_id", "target_id", "type", "index", "branch", "name"])
    for e in edges:
        w2.writerow([e[0], e[1], "AST", "", "", ""])
    return dsc_buf.getvalue(), cpg_buf.getvalue()


def _renumber(nodes, edges, offset):
    id_map = {n[0]: str(int(n[0]) + offset) for n in nodes}
    return (
        [(id_map[n[0]],) + tuple(n[1:]) for n in nodes],
        [(id_map[e[0]], id_map[e[1]]) for e in edges],
    )


def _pg3_nodes():
    # int a[3]; a[5] = x;  -> definite OOB write (pg-3 signal)
    return [
        ("1", "VARIABLEDECLARATION", "a", "", "a[3]"),
        ("2", "ARRAYSUBSCRIPTIONEXPRESSION", "", "", ""),
        ("3", "LITERAL", "5", "", ""),
        ("4", "DECLAREDREFERENCEEXPRESSION", "a", "", ""),
        ("5", "BINARYOPERATOR", "=", "", ""),
        ("6", "DECLAREDREFERENCEEXPRESSION", "x", "", ""),
    ], [
        ("2", "3"), ("2", "4"), ("5", "2"), ("5", "6"),
    ]


def _pg2_nodes():
    # int f(n) { f(n-1); }  -> unguarded bare recursion (pg-2 signal)
    return [
        ("1", "FUNCTIONDECLARATION", "f", "", ""),
        ("2", "COMPOUNDSTATEMENT", "", "", ""),
        ("3", "CALLEXPRESSION", "f", "", "f(n-1)"),
    ], [
        ("1", "2"), ("2", "3"),
    ]


def _pg1_nodes():
    # if (x = 1) printf("%d", x);  -> assign-in-condition feeding output
    return [
        ("1", "IFSTATEMENT", "", "", ""),
        ("2", "BINARYOPERATOR", "=", "", ""),
        ("3", "LITERAL", "1", "", ""),
        ("4", "DECLAREDREFERENCEEXPRESSION", "x", "", ""),
        ("5", "CALLEXPRESSION", "printf", "", 'printf("%d", x)'),
        ("6", "DECLAREDREFERENCEEXPRESSION", "x", "", ""),
    ], [
        ("1", "2"), ("2", "4"), ("2", "3"), ("1", "5"), ("5", "6"),
    ]


def _pg4_nodes():
    # CPG's own use-before-init marker (pg-4 AST signal)
    return [
        ("1", "UNINITIALIZEDVALUE", "", "", ""),
        ("2", "DECLAREDREFERENCEEXPRESSION", "y", "", ""),
    ], [
        ("2", "1"),
    ]


# ------------------------------------------------------------------ fixtures


def _write_submission(raw, problem="00000001", verdict="RUNTIME_ERROR",
                      sub="00001_00001", name="main", lang="c", nodes_edges=None):
    src_dir = raw / "progpedia" / problem / verdict / sub
    src_dir.mkdir(parents=True)
    suffix = ".c" if lang == "c" else (".cpp" if lang == "cpp" else f".{lang}")
    src = src_dir / f"{name}{suffix}"
    src.write_text("#include <stdio.h>\nint main(){return 0;}\n", encoding="utf-8")
    nodes, edges = nodes_edges or _pg3_nodes()
    dsc, cpg = _dsc_cpg(nodes, edges)
    (src_dir / f"{name}_c.dsc.csv").write_text(dsc, encoding="utf-8")
    (src_dir / f"{name}_c.cpg.csv").write_text(cpg, encoding="utf-8")
    return {
        "source_record_id": f"{problem}/{verdict}/{sub}/{src.name}",
        "dataset_source": "PROGPEDIA",
        "language": lang,
        "source_verdict": verdict,
        "source_code_path": f"progpedia/{problem}/{verdict}/{sub}/{src.name}",
        "source_code_sha256": f"{abs(hash((problem, verdict, sub, name))):064x}"[:64],
        "problem_id": f"tl-progpedia-{problem}",
    }


def _problems_row(pid="tl-progpedia-00000001"):
    return {
        "problem_id": pid,
        "statement": "Add two numbers\n",
        "sample_test_count": "2",
        "sample_tests": '[{"test_index": 1}]',
        "constraints": None,
        "difficulty": None,
        "concept_tags": None,
        "cpp_submission_count": None,
    }


# ------------------------------------------------------------------ fire_rules


def test_fire_rules_single_signals():
    flags = [{"flag": "-Wparentheses", "count": 1}]
    assert fire_rules("WRONG_ANSWER", flags, {"assign_in_condition_count": 1,
                                              "assign_feeds_output_count": 1}) == ["pg-1"]
    assert fire_rules("RUNTIME_ERROR", [], {"unguarded_recursion_count": 1}) == ["pg-2"]
    assert fire_rules("RUNTIME_ERROR", [], {"array_write_oob_count": 2}) == ["pg-3"]
    assert fire_rules("WRONG_ANSWER", [{"flag": "-Wmaybe-uninitialized", "count": 1}],
                      {"use_before_init_count": 1}) == ["pg-4"]


def test_fire_rules_respect_verdict_and_signal_gates():
    # pg-2/pg-3 need RUNTIME_ERROR; pg-1/pg-4 only non-ACCEPTED
    assert fire_rules("ACCEPTED", [], {"unguarded_recursion_count": 1}) == []
    assert fire_rules("WRONG_ANSWER", [], {"array_write_oob_count": 2}) == []
    assert fire_rules("RUNTIME_ERROR", [], {"assign_in_condition_count": 1,
                                            "assign_feeds_output_count": 1}) == []
    # pg-1 needs the warning AND feeds-output; pg-4 needs the warning
    wa = [{"flag": "-Wparentheses", "count": 1}]
    assert fire_rules("WRONG_ANSWER", wa, {"assign_in_condition_count": 1,
                                           "assign_feeds_output_count": 0}) == []
    assert fire_rules("WRONG_ANSWER", [], {"use_before_init_count": 1}) == []


def test_fire_rules_multi_signal_lists_all_rules():
    got = fire_rules("RUNTIME_ERROR", [],
                     {"unguarded_recursion_count": 1, "array_write_oob_count": 1})
    assert sorted(got) == ["pg-2", "pg-3"]


# ------------------------------------------------------------------ label_rows


def test_label_rows_pg3_produces_g1_clean_row(tmp_path):
    raw = tmp_path / "raw"
    idx = [_write_submission(raw)]
    problems = {"tl-progpedia-00000001": _problems_row()}
    labeled, review, skipped = label_rows(idx, problems, {}, raw)
    assert len(labeled) == 1 and not review
    row = labeled[0]
    assert row["label"] == "CPP_ARRAY_BOUNDS"
    assert row["label_source"] == "weak_rule"
    assert row["label_confidence"] == 0.60
    assert row["firing_functions"] == ["pg-3"]
    assert row["row_id"].startswith("pg-")
    assert row["verdict"] == "RUNTIME_ERROR"
    assert row["secondary_labels"] == []
    assert row["verified_by_execution"] is None
    assert row["meta"] == {"user_id_hash": None, "attempt_index": None,
                           "timestamp": None, "prev_submission_id": None}
    assert row["cpg"]["available"] is True
    assert row["static"]["loc"] >= 2                # static block has no available gate
    assert row["runtime"]["available"] is False     # source cannot provide -> NaN
    assert row["context"]["statement_length"] == len("Add two numbers\n")
    issues = check_row(row, {idx[0]["source_record_id"]})
    assert issues == [], issues


def test_label_rows_multi_signal_goes_to_review_pool(tmp_path):
    raw = tmp_path / "raw"
    nodes, edges = _pg3_nodes()
    nodes2, edges2 = _renumber(*_pg2_nodes(), offset=10)
    idx = [_write_submission(raw, nodes_edges=(nodes + nodes2, edges + edges2))]
    labeled, review, skipped = label_rows(idx, {}, {}, raw)
    assert labeled == []
    assert len(review) == 1
    assert not review[0].get("row_id")          # never a dataset row
    assert sorted(review[0]["candidate_labels"]) == ["CPP_ARRAY_BOUNDS",
                                                     "CPP_MISSING_BASE_CASE"]


def test_label_rows_verdict_gated_rows_stay_unlabeled(tmp_path):
    raw = tmp_path / "raw"
    idx = [_write_submission(raw, verdict="ACCEPTED")]     # pg-3 needs RE
    labeled, review, skipped = label_rows(idx, {}, {}, raw)
    assert labeled == [] and review == []
    assert skipped["no_rule_fired"] == 1


def test_label_rows_java_and_python_out_of_scope(tmp_path):
    raw = tmp_path / "raw"
    idx = [_write_submission(raw, lang="java", name="A"),
           _write_submission(raw, sub="00002_00002", lang="python", name="a")]
    labeled, review, skipped = label_rows(idx, {}, {}, raw)
    assert labeled == [] and review == []
    assert skipped["out_of_scope"] == 2


def test_label_rows_warnings_cache_feeds_pg1_and_pg4(tmp_path):
    raw = tmp_path / "raw"
    r1 = _write_submission(raw, verdict="WRONG_ANSWER", nodes_edges=_pg1_nodes())
    r4 = _write_submission(raw, sub="00002_00002", verdict="WRONG_ANSWER",
                           nodes_edges=_pg4_nodes())
    warnings = {
        r1["source_record_id"]: [{"flag": "-Wparentheses", "count": 1}],
        r4["source_record_id"]: [{"flag": "-Wmaybe-uninitialized", "count": 1},
                                 {"flag": "-Wunused-result", "count": 2}],
    }
    labeled, review, skipped = label_rows([r1, r4], {}, warnings, raw)
    by_rec = {r["source_record_id"]: r for r in labeled}
    assert by_rec[r1["source_record_id"]]["label"] == "CPP_ASSIGN_VS_COMPARE"
    assert by_rec[r1["source_record_id"]]["label_confidence"] == 0.60
    assert by_rec[r1["source_record_id"]]["firing_functions"] == ["pg-1"]
    assert by_rec[r4["source_record_id"]]["label"] == "CPP_UNINITIALIZED_VAR"
    assert by_rec[r4["source_record_id"]]["label_confidence"] == 0.55
    assert by_rec[r4["source_record_id"]]["firing_functions"] == ["pg-4"]
    # both warning blocks carry the parsed flags
    assert by_rec[r1["source_record_id"]]["warnings"]["available"] is True
    assert by_rec[r4["source_record_id"]]["warnings"]["available"] is True


def test_label_rows_null_warnings_never_guessed(tmp_path):
    # compile failed -> flags null -> pg-1/pg-4 cannot fire from absent evidence
    raw = tmp_path / "raw"
    r1 = _write_submission(raw, verdict="WRONG_ANSWER", nodes_edges=_pg1_nodes())
    labeled, review, skipped = label_rows([r1], {}, {r1["source_record_id"]: None}, raw)
    assert labeled == [] and review == []
    assert skipped["no_rule_fired"] == 1


def test_label_rows_deterministic_output(tmp_path):
    raw = tmp_path / "raw"
    idx = [_write_submission(raw), _write_submission(raw, sub="00002_00002")]
    out1, _, _ = label_rows(idx, {}, {}, raw)
    out2, _, _ = label_rows(list(reversed(idx)), {}, {}, raw)
    assert json.dumps(out1, sort_keys=True) == json.dumps(out2, sort_keys=True)
    assert [r["row_id"] for r in out1] == ["pg-000001", "pg-000002"]
