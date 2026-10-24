"""merge_dataset.py tests (master plan §7, R5 — the merge + G7 gate).

The merge is the integration point every lane feeds: validate each tier vs
G1 -> concat -> MinHash dedupe -> join label_mapping + cluster/split ->
G7 leakage checks -> labels.jsonl + features.csv + splits.csv + report.

Binding rules tested here:
- only tier*.jsonl files are lane inputs (labels.jsonl from a previous run
  is never re-merged);
- duplicate row_ids across lanes fail loudly;
- MinHash token 5-gram dedupe, Jaccard >= 0.8, keep-first deterministic;
- SYNTHETIC rows have no own code (source_record_id is the SEED, shared by
  many mutants) -> they dedupe by identity (seed_ref, mutation_op,
  problem_id, label), never by seed code;
- a labeled row whose problem has no cluster row fails (G7 integrity);
- rows inherit their problem cluster's split; clusters never straddle
  splits; seed groups never straddle splits; cross-split twins = 0;
- label_mapping join attaches family and executes pre-registered merges
  (merged_into) as a join, not a regeneration;
- features.csv columns = registry canonical names, missing blocks -> NaN.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.merge_dataset import (
    g7_checks,
    jaccard,
    merge,
    resolve_code,
    token_shingles,
)

CODE_A = (
    "int main() { int a[10]; for (int i = 0; i <= 10; i++) a[i] = i; "
    "return a[0] + a[1] + a[2] + a[3] + a[4] + a[5] + a[6] + a[7]; }"
)
CODE_A_EDIT = CODE_A.replace("return a[0]", "return a[7]")  # 1-token edit, long code
CODE_B = (
    "int sum() { int t = 0; while (t < 5) { t = t + 1; } "
    "printf(\"%d\", t); return t * 2 - 1 / t + t; }"
)

LM_HEADER = "kind,mutation_op,label,family,modeled,hard3,status,merged_into,lf_inputs"
LM_ROWS = [
    "label,,CPP_ARRAY_BOUNDS,Boundary,yes,no,active,,synthetic_ops;lf_weak;human",
    "label,,CPP_LOOP_BOUNDARY,Boundary,yes,no,active,,synthetic_ops;lf_weak;human",
    "label,,CPP_OTHER_ERROR,Other,yes,no,active,,human",
    # pre-registered merge: STALE_EXIT folds into OTHER_ERROR at merge time
    "label,,CPP_STALE_EXIT,Other,no,no,merged,CPP_OTHER_ERROR,human",
]


def _tier_row(row_id, source, srs, problem_id, label="CPP_ARRAY_BOUNDS",
              code_key=None, seed_ref=None, label_source="weak_rule"):
    row = {
        "row_id": row_id,
        "dataset_source": source,
        "source_record_id": srs,
        "problem_id": problem_id,
        "problem_cluster": None,
        "language": "c",
        "label": label,
        "label_source": label_source,
        "label_confidence": 0.6,
        "secondary_labels": [],
        "verdict": "RUNTIME_ERROR",
        "firing_functions": [],
        "seed_ref": seed_ref,
        "mutation_op": "op_x" if seed_ref else None,
        "verified_by_execution": True if label_source == "synthetic" else None,
        "meta": {},
        "pipeline_run_id": "fixture/1.0.0",
        "taxonomy_version": "tl-cpp-v2",
        "schema_version": "1.0",
        "static": {"loc": 3}, "warnings": {"available": False}, "runtime": {"available": False},
        "tests": {"available": False}, "cpg": {"available": False},
        "context": {"available": False},
    }
    if code_key:
        row["_code_key"] = code_key
    return row


def _build_dataset(tmp_path: Path, tiers: dict[str, list[dict]], clusters: list[dict],
                   raw_files: dict[str, str] | None = None,
                   index_rows: list[dict] | None = None,
                   lm_rows: list[str] | None = None) -> Path:
    """Materialize a full miniature dataset dir; returns the dataset dir."""
    ds = tmp_path / "ds"
    ann = ds / "annotations"
    ann.mkdir(parents=True)
    for name, rows in tiers.items():
        with (ann / f"{name}.jsonl").open("w", encoding="utf-8") as fh:
            for r in rows:
                r = dict(r)
                r.pop("_code_key", None)
                fh.write(json.dumps(r) + "\n")

    (ds / "label_mapping.csv").write_text(
        LM_HEADER + "\n" + "\n".join(lm_rows or LM_ROWS) + "\n", encoding="utf-8"
    )
    splits = ds / "splits"
    splits.mkdir()
    with (splits / "cluster_assignments.csv").open("w", newline="", encoding="utf-8") as fh:
        fh.write("problem_id,cluster_id,split,statement_len\n")
        for c in clusters:
            fh.write(f"{c['problem_id']},{c['cluster_id']},{c['split']},10\n")

    raw = tmp_path / "raw"
    for rel, code in (raw_files or {}).items():
        p = raw / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(code, encoding="utf-8")

    # mutant-proof corpus for SYNTHETIC rows (G1's evidence-based excuse
    # for template mutants: (problem_id, mutation_op, label) triples)
    synthetic = [r for rows_ in tiers.values() for r in rows_ if r["dataset_source"] == "SYNTHETIC"]
    if synthetic:
        proofs = ann / "mutant_proofs"
        proofs.mkdir(exist_ok=True)
        for i, r in enumerate(synthetic):
            (proofs / f"{i:08x}.json").write_text(json.dumps({
                "run_id": f"{i:08x}", "problem_id": r["problem_id"],
                "operator": r.get("mutation_op") or "", "label": r["label"],
                "mutant_sha256": f"{i:064x}", "seed_sha256": f"{i + 1:064x}",
            }), encoding="utf-8")

    # normalized index: an explicit index_rows list is EXHAUSTIVE (the
    # G1-refusal test relies on that); index_rows=None synthesizes
    # resolvable entries + raw code files for every non-SYNTHETIC row so
    # fixtures exercise the real code path without hand-wiring each test.
    entries: dict[str, str] = {}
    if index_rows is not None:
        entries = {r["source_record_id"]: r["source_code_path"] for r in index_rows}
    else:
        import hashlib as _hashlib

        for rows_ in tiers.values():
            for r in rows_:
                if r["dataset_source"] == "SYNTHETIC":
                    continue
                srs = r["source_record_id"]
                entries.setdefault(srs, f"auto/{_hashlib.sha1(srs.encode()).hexdigest()[:12]}.c")
    for rel in entries.values():
        if not rel.startswith("auto/"):
            continue
        digest = rel.removeprefix("auto/").removesuffix(".c")
        p = raw / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        # distinct code per entry: no two auto files may look like twins
        p.write_text(
            f"int auto_{digest}() {{ int v{digest[:6]} = 17; return v{digest[:6]} + 17; }}\n",
            encoding="utf-8",
        )

    idx = tmp_path / "index.csv"
    with idx.open("w", newline="", encoding="utf-8") as fh:
        fh.write("source_record_id,source_code_path\n")
        for srs, rel in entries.items():
            fh.write(f"{srs},{rel}\n")

    return ds


_CLUSTERS = [
    {"problem_id": "p-1", "cluster_id": "clu-000", "split": "train"},
    {"problem_id": "p-2", "cluster_id": "clu-001", "split": "test"},
]


def _run(ds: Path, **kw):
    # fixture layout: ds/, index.csv and raw/ are siblings under tmp_path
    return merge(
        dataset_dir=ds,
        index_csv=ds.parent / "index.csv",
        raw_root=ds.parent / "raw",
        **kw,
    )


# ------------------------------------------------------------- happy path


def test_merge_three_tiers_writes_all_outputs(tmp_path: Path):
    t0 = [_tier_row("mut-1", "SYNTHETIC", "tpl-X-001", "p-1", label_source="synthetic",
                    seed_ref="tpl-X-001")]
    t1a = [_tier_row("cs-1", "CODESTREAM", "rec-cs-1", "p-1")]
    t1b = [_tier_row("pg-1", "PROGPEDIA", "rec-pg-1", "p-2")]
    ds = _build_dataset(
        tmp_path,
        {"tier0_mutants": t0, "tier1a_codestream": t1a, "tier1b_progpedia": t1b},
        _CLUSTERS,
    )
    report = _run(ds)
    labels = [json.loads(l) for l in (ds / "annotations" / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r["row_id"] for r in labels} == {"mut-1", "cs-1", "pg-1"}
    assert all(r["problem_cluster"] in {"clu-000", "clu-001"} for r in labels)
    assert (ds / "features" / "features.csv").is_file()
    assert (ds / "splits" / "splits.csv").is_file()
    assert (ds / "reports" / "merge_report.json").is_file()
    assert report["n_rows"] == 3


def test_previous_run_labels_jsonl_is_not_remerged(tmp_path: Path):
    t1b = [_tier_row("pg-1", "PROGPEDIA", "rec-pg-1", "p-2")]
    ds = _build_dataset(tmp_path, {"tier1b_progpedia": t1b}, _CLUSTERS)
    _run(ds)
    # second run: annotations/ now contains labels.jsonl too
    report = _run(ds)
    assert report["n_rows"] == 1


def test_duplicate_row_id_across_lanes_fails(tmp_path: Path):
    t1a = [_tier_row("pg-1", "CODESTREAM", "rec-1", "p-1")]
    t1b = [_tier_row("pg-1", "PROGPEDIA", "rec-2", "p-2")]
    ds = _build_dataset(tmp_path, {"tier1a_codestream": t1a, "tier1b_progpedia": t1b}, _CLUSTERS)
    with pytest.raises(ValueError, match="row_id"):
        _run(ds)


# ----------------------------------------------------------------- dedupe


def test_token_shingles_five_grams_and_jaccard():
    a = token_shingles(CODE_A)
    b = token_shingles(CODE_A_EDIT)
    assert jaccard(a, a) == 1.0
    assert jaccard(a, set()) == 0.0
    assert jaccard(a, b) >= 0.8, "one-token edit in long code must stay >= 0.8"
    assert jaccard(a, token_shingles(CODE_B)) < 0.3


def test_minhash_dedupe_drops_near_dup_keeps_first(tmp_path: Path):
    # pg-1 and pg-2 are code twins in different problems -> one dropped
    t1b = [
        _tier_row("pg-1", "PROGPEDIA", "rec-1", "p-1", code_key="a"),
        _tier_row("pg-2", "PROGPEDIA", "rec-2", "p-2", code_key="a_edit"),
    ]
    ds = _build_dataset(
        tmp_path, {"tier1b_progpedia": t1b}, _CLUSTERS,
        raw_files={"x/a.c": CODE_A, "x/b.c": CODE_A_EDIT},
        index_rows=[
            {"source_record_id": "rec-1", "source_code_path": "x/a.c"},
            {"source_record_id": "rec-2", "source_code_path": "x/b.c"},
        ],
    )
    report = _run(ds)
    labels = [json.loads(l) for l in (ds / "annotations" / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["row_id"] for r in labels] == ["pg-1"]  # keep-first, deterministic
    assert report["deduped"] == 1


def test_different_code_survives_dedupe(tmp_path: Path):
    t1b = [
        _tier_row("pg-1", "PROGPEDIA", "rec-1", "p-1", code_key="a"),
        _tier_row("pg-2", "PROGPEDIA", "rec-2", "p-2", code_key="b"),
    ]
    ds = _build_dataset(
        tmp_path, {"tier1b_progpedia": t1b}, _CLUSTERS,
        raw_files={"x/a.c": CODE_A, "x/b.c": CODE_B},
        index_rows=[
            {"source_record_id": "rec-1", "source_code_path": "x/a.c"},
            {"source_record_id": "rec-2", "source_code_path": "x/b.c"},
        ],
    )
    report = _run(ds)
    assert report["n_rows"] == 2 and report["deduped"] == 0


def test_synthetic_rows_dedupe_by_identity_not_seed_code(tmp_path: Path):
    # Every mutant's source_record_id is the SEED, and here all seeds map to
    # the SAME code file. Identity dedupe must key on (seed_ref, mutation_op,
    # problem_id, label): distinct operators both survive, an identical
    # identity collapses — seed code must never drive the decision (a
    # seed-code implementation would collapse all four into one).
    t0 = [
        _tier_row("mut-1", "SYNTHETIC", "seed-1", "p-1", seed_ref="seed-1", label_source="synthetic"),
        _tier_row("mut-2", "SYNTHETIC", "seed-1", "p-1", seed_ref="seed-1", label_source="synthetic"),
        _tier_row("mut-3", "SYNTHETIC", "seed-2", "p-1", seed_ref="seed-2", label_source="synthetic"),
        _tier_row("mut-4", "SYNTHETIC", "seed-1", "p-1", seed_ref="seed-1", label_source="synthetic"),
    ]
    t0[1]["mutation_op"] = "op_y"  # mut-2 differs from mut-1 by operator
    ds = _build_dataset(
        tmp_path,
        {"tier0_mutants": t0},
        _CLUSTERS,
        raw_files={"seed.c": CODE_A},
        index_rows=[
            {"source_record_id": "seed-1", "source_code_path": "seed.c"},
            {"source_record_id": "seed-2", "source_code_path": "seed.c"},
        ],
    )
    report = _run(ds)
    labels = [json.loads(l) for l in (ds / "annotations" / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
    assert report["n_rows"] == 3
    assert [r["row_id"] for r in labels] == ["mut-1", "mut-2", "mut-3"]


# ------------------------------------------------------- splits + G7 joins


def test_rows_inherit_cluster_split(tmp_path: Path):
    t1b = [_tier_row("pg-1", "PROGPEDIA", "rec-1", "p-2")]  # p-2 -> test cluster
    ds = _build_dataset(tmp_path, {"tier1b_progpedia": t1b}, _CLUSTERS)
    _run(ds)
    labels = [json.loads(l) for l in (ds / "annotations" / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
    assert labels[0]["problem_cluster"] == "clu-001"
    splits = (ds / "splits" / "splits.csv").read_text(encoding="utf-8")
    assert "pg-1,p-2,clu-001,test" in splits


def test_problem_without_cluster_row_fails(tmp_path: Path):
    t1b = [_tier_row("pg-1", "PROGPEDIA", "rec-1", "p-unknown")]
    ds = _build_dataset(tmp_path, {"tier1b_progpedia": t1b}, _CLUSTERS)
    with pytest.raises(ValueError, match="cluster"):
        _run(ds)


def test_g7_seed_group_must_not_straddle_splits(tmp_path: Path):
    # two rows share a seed_ref but their problems sit in different splits
    t0 = [
        _tier_row("mut-1", "SYNTHETIC", "seed-1", "p-1", seed_ref="seed-1", label_source="synthetic"),
        _tier_row("mut-2", "SYNTHETIC", "tpl-Y-002", "p-2", seed_ref="seed-1", label_source="synthetic"),
    ]
    ds = _build_dataset(tmp_path, {"tier0_mutants": t0}, _CLUSTERS)
    _run(ds)  # merge reports G7 findings, it never silently re-splits
    results = g7_checks(*_load_merged(ds))
    assert results["seed_groups"]["ok"] is False
    assert results["seed_group_conflicts"] == 1


def _load_merged(ds: Path):
    labels = [json.loads(l) for l in (ds / "annotations" / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
    clusters = {}
    for line in (ds / "splits" / "cluster_assignments.csv").read_text(encoding="utf-8").splitlines()[1:]:
        pid, cid, split, _ = line.split(",")
        clusters[pid] = (cid, split)
    return labels, clusters


def test_g7_cluster_intersection_empty_and_twins_zero(tmp_path: Path):
    t1b = [_tier_row("pg-1", "PROGPEDIA", "rec-1", "p-1")]
    ds = _build_dataset(tmp_path, {"tier1b_progpedia": t1b}, _CLUSTERS)
    _run(ds)
    report = json.loads((ds / "reports" / "merge_report.json").read_text(encoding="utf-8"))
    g7 = report["g7"]
    assert g7["cluster_split_conflicts"] == 0
    assert g7["cross_split_twins"] == 0
    assert g7["seed_group_conflicts"] == 0


# ------------------------------------------------------- label_mapping join


def test_label_mapping_join_attaches_family(tmp_path: Path):
    t1b = [_tier_row("pg-1", "PROGPEDIA", "rec-1", "p-1")]
    ds = _build_dataset(tmp_path, {"tier1b_progpedia": t1b}, _CLUSTERS)
    _run(ds)
    labels = [json.loads(l) for l in (ds / "annotations" / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
    assert labels[0]["family"] == "Boundary"


def test_pre_registered_merge_relabels_via_join(tmp_path: Path):
    t1a = [_tier_row("cs-1", "CODESTREAM", "rec-1", "p-1", label="CPP_STALE_EXIT")]
    ds = _build_dataset(tmp_path, {"tier1a_codestream": t1a}, _CLUSTERS)
    report = _run(ds)
    labels = [json.loads(l) for l in (ds / "annotations" / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
    assert labels[0]["label"] == "CPP_OTHER_ERROR"
    assert report["merged_labels"] == 1


# ------------------------------------------------------------- features.csv


def test_features_csv_columns_match_registry(tmp_path: Path):
    from tracelearn_features.schema import feature_names

    t1b = [_tier_row("pg-1", "PROGPEDIA", "rec-1", "p-1")]
    ds = _build_dataset(tmp_path, {"tier1b_progpedia": t1b}, _CLUSTERS)
    _run(ds)
    header = (ds / "features" / "features.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header[:2] == ["row_id", "label"]
    assert header[2:] == feature_names()


def test_missing_blocks_flatten_to_nan(tmp_path: Path):
    t1b = [_tier_row("pg-1", "PROGPEDIA", "rec-1", "p-1")]
    ds = _build_dataset(tmp_path, {"tier1b_progpedia": t1b}, _CLUSTERS)
    _run(ds)
    line = (ds / "features" / "features.csv").read_text(encoding="utf-8").splitlines()[1]
    cols = line.split(",")
    assert cols[0] == "pg-1" and cols[1] == "CPP_ARRAY_BOUNDS"
    assert cols[2] == "3"           # static.loc present
    i = header_index(ds, "warnings.total")
    assert cols[i] == "" or cols[i].lower() == "nan"  # missing -> NaN


def header_index(ds: Path, name: str) -> int:
    header = (ds / "features" / "features.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    return header.index(name)


# --------------------------------------------------------------- code paths


def test_resolve_code_codestream_csv_ref(tmp_path: Path):
    raw = tmp_path / "raw"
    csv_path = raw / "cs" / "Submission Data.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_text(
        "submission_id,source_code\nrec-1,\"int main(){int z = 1; return z;}\"\n",
        encoding="utf-8",
    )
    row = {"source_record_id": "rec-1", "dataset_source": "CODESTREAM",
           "source_code_path": "cs/Submission Data.csv#rec-1"}
    assert "int z = 1" in resolve_code(row, raw)


def test_resolve_code_plain_path(tmp_path: Path):
    raw = tmp_path / "raw"
    p = raw / "progpedia" / "a.c"
    p.parent.mkdir(parents=True)
    p.write_text("int main(){return 0;}", encoding="utf-8")
    row = {"source_record_id": "rec", "dataset_source": "PROGPEDIA",
           "source_code_path": "progpedia/a.c"}
    assert resolve_code(row, raw) == "int main(){return 0;}"


def test_resolve_code_synthetic_is_none():
    row = {"source_record_id": "seed-1", "dataset_source": "SYNTHETIC",
           "source_code_path": "cs/Submission Data.csv#seed-1"}
    assert resolve_code(row, Path("/nonexistent")) is None


def test_unresolvable_code_is_kept_not_dropped(tmp_path: Path):
    # code cannot be read -> row is kept (never silently dropped) and
    # reported as code-uncovered
    t1b = [_tier_row("pg-1", "PROGPEDIA", "rec-1", "p-1")]
    ds = _build_dataset(tmp_path, {"tier1b_progpedia": t1b}, _CLUSTERS,
                        index_rows=[{"source_record_id": "rec-1", "source_code_path": "gone.c"}])
    report = _run(ds)
    assert report["n_rows"] == 1
    assert report["code_uncovered"] == 1


# -------------------------------------------------------------------- PSI


def test_psi_identical_low_disjoint_high():
    from scripts.merge_dataset import psi

    same = [1.0, 2.0, 3.0, 4.0, 5.0] * 4
    other = [90.0, 91.0, 92.0, 93.0, 94.0] * 4
    assert psi(same, same) < 0.01
    assert psi(same, other) > 0.2


def test_merge_refuses_g1_invalid_rows(tmp_path: Path):
    # a non-synthetic row whose source_record_id is absent from the index
    # (index_rows=[] -> explicitly empty) is an orphan: merge must refuse to
    # merge invalid lanes, never emit a partial dataset.
    t1b = [_tier_row("pg-1", "PROGPEDIA", "rec-x", "p-1")]
    ds = _build_dataset(tmp_path, {"tier1b_progpedia": t1b}, _CLUSTERS, index_rows=[])
    with pytest.raises(ValueError, match="G1"):
        _run(ds)
    assert not (ds / "annotations" / "labels.jsonl").exists()


def test_psi_runs_when_both_splits_have_enough_rows(tmp_path: Path):
    # >=10 train AND >=10 test rows carrying static.loc: the merge must
    # actually compute PSI (a wiring bug keying numeric features by short
    # name instead of canonical name silently yields checked=0).
    t1b = [_tier_row(f"pg-{i:03d}", "PROGPEDIA", f"rec-t{i}", "p-1") for i in range(10)]
    t1b += [_tier_row(f"pg-1{i:02d}", "PROGPEDIA", f"rec-e{i}", "p-2") for i in range(10)]
    ds = _build_dataset(tmp_path, {"tier1b_progpedia": t1b}, _CLUSTERS)
    report = _run(ds)
    assert report["n_rows"] == 20
    assert report["psi"]["n_features_checked"] >= 1
    assert report["psi"]["max"] is not None
    # identical constant distributions -> no drift violation
    assert report["psi"]["violations"] == []


def test_availability_flag_false_is_not_counted_as_populated(tmp_path: Path):
    # `available: false` means the lane did not measure the block. It must
    # not inflate the per-source availability report to 100%.
    pg = [_tier_row("pg-001", "PROGPEDIA", "rec-1", "p-1")]
    pg[0]["runtime"] = {"available": False}
    pg[0]["tests"] = {"available": False}
    pg[0]["warnings"] = {"available": False}
    ds = _build_dataset(tmp_path, {"tier1b_progpedia": pg}, _CLUSTERS)
    report = _run(ds)
    avail = report["feature_availability"]
    assert avail["runtime"]["PROGPEDIA"] == 0.0
    assert avail["tests"]["PROGPEDIA"] == 0.0
    assert avail["warnings"]["PROGPEDIA"] == 0.0
    assert avail["static"]["PROGPEDIA"] == 1.0


def test_feature_availability_matrix_reports_lane_gaps(tmp_path: Path):
    # tier1a reality: static=null for all CodeStream rows -> the report
    # must show per-block fill rates per source so lane gaps are visible.
    a = _tier_row("pg-001", "PROGPEDIA", "rec-1", "p-1")
    b = _tier_row("pg-002", "PROGPEDIA", "rec-2", "p-1")
    b["static"] = None  # a row whose static block was never mined
    ds = _build_dataset(tmp_path, {"tier1b_progpedia": [a, b]}, _CLUSTERS)
    report = _run(ds)
    avail = report["feature_availability"]
    assert avail["static"]["PROGPEDIA"] == 0.5
    assert set(avail) <= {
        "static", "warnings", "runtime", "tests", "cpg", "semantics", "context"
    }


# --------------------------------------------------- lane-evidence normalization


def test_merge_mines_synthetic_embedded_code_into_features_csv(tmp_path: Path):
    # tier0 reality: static only carries the mutant's source_code + loc;
    # the merge must run the canonical extractor, not copy the raw block.
    t0 = [_tier_row("mut-1", "SYNTHETIC", "tpl-X-001", "p-1",
                    label_source="synthetic", seed_ref="tpl-X-001")]
    t0[0]["static"] = {"source_code": CODE_A, "loc": 2}
    t0[0]["warnings"] = {
        "compile_warnings": "x.cpp:1:1: warning: suggest parentheses [-Wparentheses]\n"
    }
    t0[0]["runtime"] = {"tests_passed": 1, "tests_failed": 2, "tests_total": 3,
                        "sanitizer_ok": False}
    ds = _build_dataset(tmp_path, {"tier0_mutants": t0}, _CLUSTERS)
    _run(ds)

    header = (ds / "features" / "features.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    cols = (ds / "features" / "features.csv").read_text(encoding="utf-8").splitlines()[1].split(",")
    rec = dict(zip(header, cols))
    assert rec["static.loc"] == "2"                 # lane value preserved
    assert rec["static.loop_count"] == "1"          # mined from embedded code
    assert int(rec["static.array_decl_count"]) >= 1
    assert rec["warnings.parentheses"] == "1"       # parsed from gcc text
    assert rec["tests.total"] == "3"                # bridged from runtime.*_total
    assert rec["tests.pass_rate"] == str(1 / 3)
    assert rec["semantics.loop_le"] == "1"          # mined from embedded code
    assert rec["semantics.increment"] == "1"


def test_merge_normalizes_codestream_raw_evidence(tmp_path: Path):
    t1a = [_tier_row("cs-1", "CODESTREAM", "rec-cs-1", "p-1")]
    t1a[0]["static"] = None
    t1a[0]["warnings"] = {"-Wparentheses": 2}
    t1a[0]["runtime"] = {
        "any_crash": True, "any_timeout": False, "signals": [11],
        "stack_overflow": False, "max_seconds": 0.25,
        "sanitizer": {"complete": True, "kinds": {"asan:heap-buffer-overflow": 1},
                      "reports": [{"tool": "asan", "kind": "heap-buffer-overflow"}]},
        "valgrind": {"complete": True, "kinds": {}, "uninit": False, "error_count": 0},
    }
    t1a[0]["tests"] = {
        "total": 2, "passed": 1,
        "results": [{"status": "pass"},
                    {"status": "wrong", "diff": {"numeric_deltas": [3]}}],
    }
    ds = _build_dataset(
        tmp_path,
        {"tier1a_codestream": t1a},
        _CLUSTERS,
        raw_files={"cs.c": CODE_A},
        index_rows=[{"source_record_id": "rec-cs-1", "source_code_path": "cs.c"}],
    )
    _run(ds)

    header = (ds / "features" / "features.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    cols = (ds / "features" / "features.csv").read_text(encoding="utf-8").splitlines()[1].split(",")
    rec = dict(zip(header, cols))
    assert rec["static.sloc"] == "1"                # mined from resolved own code
    assert rec["runtime.crashed"] == "1"
    assert rec["runtime.asan_heap_buffer_overflow"] == "1"
    assert rec["warnings.parentheses"] == "2"       # raw -Wflag key -> canonical
    assert rec["tests.passed"] == "1"               # status vocabulary mapped
    assert rec["tests.wrong_answer_count"] == "1"
    assert rec["tests.first_fail_numeric_diff"] == "3.0"
    assert rec["semantics.loop_le"] == "1"          # mined from resolved code
    assert rec["semantics.increment"] == "1"


def test_g7_all_ok_is_structural_only_psi_is_reported_not_gating():
    # Plan G7's PSI<0.2 gate is specified for train/val (same pool); the
    # merge's train-vs-test probe reveals pool asymmetry and is reported,
    # but must not fail a structurally clean merge.
    from scripts.merge_dataset import g7_all_ok

    clean = {
        "g7": {"cluster_split_conflicts": 0, "seed_group_conflicts": 0, "cross_split_twins": 0},
        "psi": {"violations": [{"feature": "tests.total", "psi": 3.7}]},
    }
    assert g7_all_ok(clean) is True
    dirty = {
        "g7": {"cluster_split_conflicts": 1, "seed_group_conflicts": 0, "cross_split_twins": 0},
        "psi": {"violations": []},
    }
    assert g7_all_ok(dirty) is False
    leaky = {
        "g7": {"cluster_split_conflicts": 0, "seed_group_conflicts": 0, "cross_split_twins": 2},
        "psi": {"violations": []},
    }
    assert g7_all_ok(leaky) is False
