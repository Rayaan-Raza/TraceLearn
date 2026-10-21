import json
import shutil
from pathlib import Path

from check_lane_b_artifacts import check

ROOT = Path(__file__).resolve().parents[2]


def _copy_tree(tmp: Path) -> Path:
    ds = ROOT / "data" / "misconception_dataset"
    dst = tmp / "data" / "misconception_dataset"
    (dst / "splits").mkdir(parents=True)
    (dst / "annotations" / "review").mkdir(parents=True)
    shutil.copy(ds / "splits" / "codestream_clusters.csv", dst / "splits")
    return dst


def _row(**kw):
    r = {"row_id": "cs-000001", "dataset_source": "CODESTREAM", "source_record_id": "x",
         "problem_id": "tl-codestream-prob_002", "problem_cluster": "cs-clu-002", "split_pool": "train",
         "language": "cpp", "label": "CPP_OFF_BY_ONE", "label_source": "weak_rule", "label_confidence": 0.2,
         "secondary_labels": [], "firing_functions": ["lf_off_by_one"], "verified_by_execution": False,
         "repair": None, "meta": {}, "runtime": {}, "tests": {}, "pipeline_run_id": "run-1",
         "taxonomy_version": "tl-cpp-v2", "schema_version": "1.0"}
    r.update(kw)
    return r


def _write(dst, rows):
    with open(dst / "annotations" / "tier1a_codestream.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_committed_artifacts_pass():
    assert check(ROOT) == []


def test_good_row_passes(tmp_path):
    dst = _copy_tree(tmp_path)
    _write(dst, [_row()])
    assert check(tmp_path) == []


def test_bad_rows_are_caught(tmp_path):
    dst = _copy_tree(tmp_path)
    _write(dst, [
        _row(row_id="cs-1", split_pool="test"),                     # pool disagrees with split
        _row(row_id="cs-2", label="CPP_OTHER_ERROR"),               # automatic OTHER
        _row(row_id="cs-3", label_source="repair_verified"),        # no repair proof
        _row(row_id="cs-4", label_confidence=0.95),                 # above cap
        _row(row_id="cs-5", code="int main(){}"),                   # embeds code
    ])
    errs = check(tmp_path)
    for rid in ("cs-1", "cs-2", "cs-3", "cs-4", "cs-5"):
        assert any(f"tier1a {rid}:" in e for e in errs), rid
