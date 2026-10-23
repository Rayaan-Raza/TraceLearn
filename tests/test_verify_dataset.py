"""G1 resolvers + Layer-2 per-class report tests (master plan §9.0 G1, §8).

verify_dataset.py is the R2 gate runner. It must:

G1 ("resolvers"):
- labels <-> normalized join: every row's source_record_id resolves in the
  normalized submissions index (0 orphans) — this is the traceability chain
  row_id -> lane JSONL -> raw file (§424);
- enums clean: label, label_source, dataset_source, language, taxonomy_version
  all from their frozen vocabularies; row_id prefix matches dataset_source
  (mut-/cs-/pg-, §5);
- schema_version present (non-null) on every row;
- label_confidence (when present) within [0, 1]; secondary_labels a list.

Layer 2 weekly gate ("--per-class-report"):
- prints class x lane x (certain/silver); certain = execution-verified
  synthetic + repair_verified + human (Layer 4), silver = weak_rule;
- a class whose total-certain count is below its §8 certain floor is flagged
  under-floor.

R2 milestone: green on a synthetic end-to-end row (features computed via the
pinned tracelearn_features v0 interface), red on any broken row.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_dataset import (
    CERTAIN_FLOOR,
    check_row,
    load_jsonl,
    main,
    per_class_report,
    verify,
)
from tracelearn_features import extract_features

# A normalized-index source_record_id the fixture seed resolves against.
SEED_RECORD_ID = "eeb8f10d-e3d9-4b1e-9149-87ececf9f265-28078363"

NORMALIZED_IDS = {SEED_RECORD_ID, "00000006/ACCEPTED/00002_00005/Prob_F.c"}

_SOURCE = (
    "#include <stdio.h>\n"
    "int main() {\n"
    "    int a[10];\n"
    "    for (int i = 0; i < 10; i++) {\n"
    "        if (i) { a[i] = i; }\n"
    "    }\n"
    "    return 0;\n"
    "}\n"
)


def _make_row(**overrides) -> dict:
    """A fully-valid synthetic end-to-end row; override fields for RED cases."""
    blocks = extract_features(_SOURCE, "cpp")
    row = {
        "row_id": "mut-000101",
        "dataset_source": "SYNTHETIC",
        "source_record_id": SEED_RECORD_ID,
        "problem_id": "prob_006",
        "problem_cluster": None,
        "language": "cpp",
        "label": "CPP_LOOP_BOUNDARY",
        "label_source": "synthetic",
        "label_confidence": 0.93,
        "secondary_labels": [],
        "verdict": None,
        "firing_functions": ["verify_boundary_diff"],
        "seed_ref": SEED_RECORD_ID,
        "mutation_op": "for_le_bound_lt_n1",
        "verified_by_execution": True,
        "meta": {"user_id_hash": "u-abc", "attempt_index": 3},
        "pipeline_run_id": "run-fixture-1",
        "taxonomy_version": "tl-cpp-v2",
        "schema_version": "1.0",
        **blocks,
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------- G1 checks


def test_valid_synthetic_end_to_end_row_is_green():
    report = verify([_make_row()], NORMALIZED_IDS)
    assert report.issues == [], [i.detail for i in report.issues]
    assert report.n_rows == 1


def test_missing_schema_version_fails():
    row = _make_row(schema_version=None)
    issues = check_row(row, NORMALIZED_IDS)
    assert any("schema_version" in i.check for i in issues)


def test_schema_version_absent_key_fails():
    row = _make_row()
    del row["schema_version"]
    issues = check_row(row, NORMALIZED_IDS)
    assert any("schema_version" in i.check for i in issues)


def test_bad_label_enum_fails():
    issues = check_row(_make_row(label="CPP_TIME_LIMIT"), NORMALIZED_IDS)
    assert any(i.check == "enum:label" for i in issues)


def test_no_misconception_label_is_allowed():
    row = _make_row(label="NO_MISCONCEPTION")
    issues = check_row(row, NORMALIZED_IDS)
    assert [i for i in issues if i.check == "enum:label"] == []


def test_bad_label_source_fails():
    issues = check_row(_make_row(label_source="guessed"), NORMALIZED_IDS)
    assert any(i.check == "enum:label_source" for i in issues)


def test_bad_language_fails():
    issues = check_row(_make_row(language="python"), NORMALIZED_IDS)
    assert any(i.check == "enum:language" for i in issues)


def test_bad_taxonomy_version_fails():
    issues = check_row(_make_row(taxonomy_version="tl-cpp-v1"), NORMALIZED_IDS)
    assert any(i.check == "enum:taxonomy_version" for i in issues)


def test_bad_dataset_source_fails():
    issues = check_row(_make_row(dataset_source="PROJECT_CODENET"), NORMALIZED_IDS)
    assert any(i.check == "enum:dataset_source" for i in issues)


def test_row_id_prefix_mismatch_fails():
    # cs- prefix implies CODESTREAM, but the source says SYNTHETIC.
    issues = check_row(_make_row(row_id="cs-000101"), NORMALIZED_IDS)
    assert any(i.check == "row_id_prefix" for i in issues)


def test_label_confidence_out_of_range_fails():
    issues = check_row(_make_row(label_confidence=1.7), NORMALIZED_IDS)
    assert any(i.check == "label_confidence" for i in issues)


def test_orphan_source_record_id_fails():
    issues = check_row(_make_row(source_record_id="not-in-index"), NORMALIZED_IDS)
    assert any(i.check == "join:orphan" for i in issues)


def test_progpedia_row_resolves_against_normalized_index():
    row = _make_row(
        row_id="pg-000042",
        dataset_source="PROGPEDIA",
        source_record_id="00000006/ACCEPTED/00002_00005/Prob_F.c",
        label="CPP_ARRAY_BOUNDS",
        label_source="weak_rule",
        label_confidence=0.42,
        verified_by_execution=None,
    )
    assert check_row(row, NORMALIZED_IDS) == []


def test_malformed_jsonl_line_is_reported_not_raised(tmp_path: Path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        json.dumps(_make_row()) + "\n" + "{not valid json}\n", encoding="utf-8"
    )
    rows, parse_issues = load_jsonl(path)
    assert len(rows) == 1
    assert any("json" in i.check for i in parse_issues)


def test_verify_aggregates_issues_across_rows():
    rows = [_make_row(), _make_row(label="CPP_TIME_LIMIT"), _make_row(row_id="cs-1")]
    report = verify(rows, NORMALIZED_IDS)
    assert report.n_rows == 3
    assert len(report.issues) == 2


# ------------------------------------------------------- per-class report


def test_per_class_report_certain_vs_silver():
    rows = [
        _make_row(),  # synthetic + verified -> certain
        _make_row(row_id="cs-001", dataset_source="CODESTREAM", source_record_id="x",
                  label_source="weak_rule", verified_by_execution=None),
        _make_row(row_id="pg-001", dataset_source="PROGPEDIA", source_record_id="y",
                  label_source="human", verified_by_execution=None),
    ]
    report = per_class_report(rows)
    entry = report["CPP_LOOP_BOUNDARY"]
    assert entry["certain"] == 2          # synthetic-verified + human
    assert entry["silver"] == 1           # weak_rule
    assert entry["floor"] == CERTAIN_FLOOR["CPP_LOOP_BOUNDARY"]
    assert entry["under_floor"] is True   # 2 < 300
    assert entry["by_lane"]["SYNTHETIC"]["certain"] == 1
    assert entry["by_lane"]["CODESTREAM"]["silver"] == 1
    assert entry["by_lane"]["PROGPEDIA"]["certain"] == 1


def test_synthetic_without_execution_is_silver_not_certain():
    rows = [_make_row(verified_by_execution=False)]
    entry = per_class_report(rows)["CPP_LOOP_BOUNDARY"]
    assert entry["certain"] == 0
    assert entry["silver"] == 1


def test_per_class_report_at_floor_is_not_under():
    floor = CERTAIN_FLOOR["CPP_LOOP_BOUNDARY"]
    rows = [
        _make_row(row_id=f"mut-{i:06d}", source_record_id=f"s{i}")
        for i in range(floor)
    ]
    entry = per_class_report(rows)["CPP_LOOP_BOUNDARY"]
    assert entry["certain"] == floor
    assert entry["under_floor"] is False


def test_per_class_report_includes_every_modeled_label():
    report = per_class_report([_make_row()])
    for label in (
        "CPP_LOOP_BOUNDARY", "CPP_OFF_BY_ONE", "CPP_ARRAY_BOUNDS",
        "CPP_UNINITIALIZED_VAR", "CPP_INT_OVERFLOW", "CPP_MISSING_BASE_CASE",
        "CPP_ASSIGN_VS_COMPARE", "CPP_WRONG_LOOP_DIR", "CPP_RANGE_CHECK",
        "CPP_STALE_EXIT", "CPP_OTHER_ERROR",
    ):
        assert label in report


# ------------------------------------------------------------------- CLI


def test_main_exits_zero_on_valid_rows(tmp_path: Path):
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "tier0_mutants.jsonl").write_text(
        json.dumps(_make_row()) + "\n", encoding="utf-8"
    )
    idx = tmp_path / "normalized_ids.txt"
    idx.write_text(SEED_RECORD_ID + "\n", encoding="utf-8")
    assert main(["--dataset-dir", str(ds), "--normalized-ids", str(idx)]) == 0


def test_main_exits_nonzero_on_broken_row(tmp_path: Path):
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "tier0_mutants.jsonl").write_text(
        json.dumps(_make_row(label="CPP_TIME_LIMIT")) + "\n", encoding="utf-8"
    )
    idx = tmp_path / "normalized_ids.txt"
    idx.write_text(SEED_RECORD_ID + "\n", encoding="utf-8")
    assert main(["--dataset-dir", str(ds), "--normalized-ids", str(idx)]) == 1


def test_main_fails_when_normalized_join_column_is_empty(tmp_path: Path, capsys):
    # An empty join column must NOT report "0 orphans" (a false green).
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "tier0_mutants.jsonl").write_text(
        json.dumps(_make_row()) + "\n", encoding="utf-8"
    )
    idx = tmp_path / "normalized_ids.txt"
    idx.write_text("", encoding="utf-8")
    assert main(["--dataset-dir", str(ds), "--normalized-ids", str(idx)]) == 1
    assert "empty" in capsys.readouterr().out.lower()


def test_main_per_class_report_prints_floors(tmp_path: Path, capsys):
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "tier0_mutants.jsonl").write_text(
        json.dumps(_make_row()) + "\n", encoding="utf-8"
    )
    idx = tmp_path / "normalized_ids.txt"
    idx.write_text(SEED_RECORD_ID + "\n", encoding="utf-8")
    rc = main(
        ["--dataset-dir", str(ds), "--normalized-ids", str(idx), "--per-class-report"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "CPP_LOOP_BOUNDARY" in out
    assert "certain" in out.lower()


# ------------------------------------------- synthetic proof-join exception
#
# Ruling (2026-10-23, three-lane merge): template-derived SYNTHETIC mutants
# have no real submission to point at (source_record_id = tpl-XX-NNN). Their
# provenance is the committed mutant proof corpus. G1 therefore accepts a
# SYNTHETIC row whose source_record_id is orphaned iff a proof matches its
# (problem_id, mutation_op, label) � evidence-based, never blanket. All other
# sources keep the strict normalized join.


def test_template_synthetic_row_passes_with_matching_proof():
    row = _make_row(source_record_id="tpl-LB-001", seed_ref="tpl-LB-001")
    proofs = {("prob_006", "for_le_bound_lt_n1", "CPP_LOOP_BOUNDARY")}
    report = verify([row], set(), proof_keys=proofs)
    assert report.issues == [], [i.detail for i in report.issues]


def test_template_synthetic_row_without_proof_is_still_an_orphan():
    row = _make_row(source_record_id="tpl-LB-001", seed_ref="tpl-LB-001")
    report = verify([row], set(), proof_keys=set())
    assert any(i.check == "join:orphan" for i in report.issues)


def test_synthetic_orphan_not_excused_when_proof_label_disagrees():
    row = _make_row(source_record_id="tpl-LB-001")
    proofs = {("prob_006", "for_le_bound_lt_n1", "CPP_OFF_BY_ONE")}  # other label
    issues = check_row(row, set(), proof_keys=proofs)
    assert any(i.check == "join:orphan" for i in issues)


def test_non_synthetic_orphan_never_excused_by_proofs():
    row = _make_row(
        row_id="pg-000001", dataset_source="PROGPEDIA",
        source_record_id="00000006/RUNTIME_ERROR/x/A.c", label_source="weak_rule",
        verified_by_execution=None,
    )
    proofs = {("prob_006", "for_le_bound_lt_n1", "CPP_LOOP_BOUNDARY")}
    issues = check_row(row, set(), proof_keys=proofs)
    assert any(i.check == "join:orphan" for i in issues)


def test_cli_loads_proof_keys_from_proofs_dir(tmp_path: Path):
    # main() with --proofs-dir must accept an orphaned template row when a
    # matching proof json exists in that directory.
    proofs = tmp_path / "mutant_proofs"
    proofs.mkdir()
    (proofs / "ab12cd34.json").write_text(json.dumps({
        "run_id": "ab12cd34", "problem_id": "prob_006",
        "operator": "for_le_bound_lt_n1", "label": "CPP_LOOP_BOUNDARY",
        "mutant_sha256": "f" * 64, "seed_sha256": "e" * 64,
    }), encoding="utf-8")

    ann = tmp_path / "annotations"
    ann.mkdir()
    row = _make_row(source_record_id="tpl-LB-001", seed_ref="tpl-LB-001")
    (ann / "tier0_mutants.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    idx = tmp_path / "ids.txt"
    idx.write_text(SEED_RECORD_ID + "\n", encoding="utf-8")

    rc = main(["--dataset-dir", str(tmp_path), "--normalized-ids", str(idx),
               "--proofs-dir", str(proofs)])
    assert rc == 0


def test_default_scan_excludes_merge_output_labels_jsonl(tmp_path: Path, capsys):
    # labels.jsonl is the merge's derived output; the lane gate must scan
    # tier inputs only or per-class floor counts double every row.
    ann = tmp_path / "annotations"
    ann.mkdir()
    row = _make_row()
    (ann / "tier1b_progpedia.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    (ann / "labels.jsonl").write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")

    idx = tmp_path / "ids.txt"
    idx.write_text(SEED_RECORD_ID + "\n", encoding="utf-8")

    rc = main(["--dataset-dir", str(tmp_path), "--normalized-ids", str(idx)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "across 1 file(s)" in out, out
    assert "rows scanned: 1 " in out, out
