"""IID hold-out: eligibility, stratified draw, and the merge's split override."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_iid_holdout as iid  # noqa: E402

from scripts.merge_dataset import row_split  # noqa: E402


def _rows():
    rows = []
    for i in range(30):
        rows.append({"row_id": f"pg-{i:03d}", "dataset_source": "PROGPEDIA", "problem_id": "p1",
                     "source_record_id": f"r{i}", "label": "CPP_ARRAY_BOUNDS" if i < 20 else "CPP_INT_OVERFLOW"})
    rows.append({"row_id": "cs-1", "dataset_source": "CODESTREAM", "problem_id": "p1", "source_record_id": "seed",
                 "label": "CPP_OFF_BY_ONE"})
    rows.append({"row_id": "mut-1", "dataset_source": "SYNTHETIC", "problem_id": "p1", "source_record_id": "seed",
                 "seed_ref": "seed", "label": "CPP_OFF_BY_ONE"})
    rows.append({"row_id": "pg-dev", "dataset_source": "PROGPEDIA", "problem_id": "p2", "source_record_id": "x",
                 "label": "CPP_ARRAY_BOUNDS"})
    return rows


def test_eligibility_excludes_synthetic_seeds_and_held_out_clusters():
    rows = _rows()
    split_of = {r["row_id"]: ("dev_gold" if r["problem_id"] == "p2" else "train") for r in rows}
    pool = {r["row_id"] for r in iid.eligible(rows, split_of)}
    assert "mut-1" not in pool and "cs-1" not in pool  # cs-1 seeds a mutant
    assert "pg-dev" not in pool
    assert len(pool) == 30


def test_stratified_pick_is_seeded_and_proportional():
    pool = [r for r in _rows() if r["row_id"].startswith("pg-0")]
    a = iid.stratified_pick(pool, 6, 1)
    b = iid.stratified_pick(pool, 6, 1)
    assert [r["row_id"] for r in a] == [r["row_id"] for r in b]
    assert len(a) == 6
    assert sum(r["label"] == "CPP_ARRAY_BOUNDS" for r in a) == 4


def test_row_split_override_only_from_train():
    clusters = {"p1": ("clu-1", "train"), "p2": ("clu-2", "dev_gold")}
    assert row_split({"row_id": "pg-1", "problem_id": "p1"}, clusters, {"pg-1"}) == "test_iid"
    assert row_split({"row_id": "pg-2", "problem_id": "p1"}, clusters, {"pg-1"}) == "train"
    with pytest.raises(ValueError):
        row_split({"row_id": "pg-3", "problem_id": "p2"}, clusters, {"pg-3"})
