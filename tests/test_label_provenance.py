"""U1 provenance derivation tests."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from label_provenance import build_rows, derive_provenance, main


def row(**kw):
    base = {"row_id": "r", "dataset_source": "PROGPEDIA", "label_source": "human"}
    base.update(kw)
    return base


def test_synthetic():
    p = derive_provenance(row(dataset_source="SYNTHETIC", label_source="synthetic"))
    assert p == {"code_origin": "synthetic_mutant", "label_origin": "synthetic_by_construction", "reviewer_type": "none"}


def test_blind_review_is_assumed_human():
    p = derive_provenance(row(dataset_source="CODESTREAM", label_status="blind_review",
                              audit={"signed_off_by": "assumed-human (blind labels by a model-assisted reviewer; owner instruction 2026-11-07)"}))
    assert (p["label_origin"], p["reviewer_type"]) == ("blind_review", "human_assumed")


def test_agent_consensus():
    p = derive_provenance(row(label_status="agent_consensus", audit={"signed_off_by": "agent consensus (x)"}))
    assert (p["label_origin"], p["reviewer_type"]) == ("agent_consensus", "model_agents")


def test_review_overlay_signed_and_assumed():
    s = derive_provenance(row(label_status="agent_consensus", review={"basis": "human", "signed_off_by": "Umaima"}))
    a = derive_provenance(row(review={"basis": "human", "signed_off_by": "assumed-human (project owner instruction)"}))
    assert (s["label_origin"], s["reviewer_type"]) == ("human_review", "human_signed")
    assert a["reviewer_type"] == "human_assumed"


def test_legacy_human_flag_unrecorded():
    p = derive_provenance(row())
    assert (p["label_origin"], p["reviewer_type"]) == ("legacy_human_flag", "none_recorded")


def test_weak_and_repair():
    assert derive_provenance(row(label_source="weak_rule"))["label_origin"] == "weak_rule"
    assert derive_provenance(row(label_status="repair_verified"))["reviewer_type"] == "execution"


def test_sidecar_roundtrip_and_check(tmp_path):
    ann = tmp_path / "annotations"
    ann.mkdir()
    (ann / "labels.jsonl").write_text(json.dumps(row(row_id="a")) + "\n" + json.dumps(row(row_id="b", label_status="weak_rule")) + "\n")
    assert [r["row_id"] for r in build_rows(ann / "labels.jsonl")] == ["a", "b"]
    assert main(["--dataset-dir", str(tmp_path), "--check"]) == 1
    assert main(["--dataset-dir", str(tmp_path)]) == 0
    assert main(["--dataset-dir", str(tmp_path), "--check"]) == 0


# ---- U1: filters keep their row sets -------------------------------------------------------------

import csv as _csv
from label_provenance import has_human_flag_origin, is_human_signed

_DS = Path(__file__).resolve().parents[1] / "data" / "misconception_dataset"
_LABELS = _DS / "annotations" / "labels.jsonl"


def _committed_rows():
    if not _LABELS.exists():
        import pytest
        pytest.skip("labels.jsonl not present")
    return [json.loads(line) for line in _LABELS.open(encoding="utf-8") if line.strip()]


def test_origin_list_selects_exactly_the_old_human_flag_rows():
    """The explicit label_origin list must give the same row ids as `label_source == "human"`."""
    rows = _committed_rows()
    old = {r["row_id"] for r in rows if r.get("label_source") == "human"}
    new = {r["row_id"] for r in rows if has_human_flag_origin(r)}
    assert new == old and len(old) > 2000


def test_trainer_selects_the_identical_row_ids():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.train_xgb_misconception import PLAIN_EXCLUDED_PREFIXES, PLAIN_SYNTHETIC_PREFIXES, plain_row_selected

    def old(row_id, row):  # the selection before U1
        if row["dataset_source"] == "SYNTHETIC":
            return row_id.startswith(PLAIN_SYNTHETIC_PREFIXES) and not row_id.startswith(PLAIN_EXCLUDED_PREFIXES)
        return row.get("label_source") == "human"

    rows = _committed_rows()
    assert {r["row_id"] for r in rows if plain_row_selected(r["row_id"], r)} == \
           {r["row_id"] for r in rows if old(r["row_id"], r)}


def test_signed_rows_are_a_strict_subset_of_the_human_flag():
    rows = _committed_rows()
    signed = {r["row_id"] for r in rows if is_human_signed(r)}
    flagged = {r["row_id"] for r in rows if r.get("label_source") == "human"}
    assert signed and signed < flagged
