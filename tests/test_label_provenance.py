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
