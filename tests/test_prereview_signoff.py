"""Sign-off rules for model pre-review sheets and the merge's review-decision hook."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import apply_prereview_signoff as ap  # noqa: E402
from prereview_common import mark_spotcheck  # noqa: E402

from scripts.merge_dataset import apply_review_decisions  # noqa: E402


def _row(i, verdict="", human_label="", spot="0", model_label="CPP_OFF_BY_ONE", model_verdict="correct"):
    return {"item_id": f"X-{i}", "model_label": model_label, "model_verdict": model_verdict,
            "human_verdict": verdict, "human_label": human_label, "spotcheck": spot}


def test_unsigned_sheet_decides_nothing():
    rows = [_row(i, spot="1" if i < 2 else "0") for i in range(10)]
    st = ap.sheet_status(rows)
    assert st["signed"] == 0 and not st["accepted_on_spotcheck"]
    assert all(ap.decide_row(r, st["accepted_on_spotcheck"]) == (None, None) for r in rows)


def test_spotcheck_acceptance_needs_all_spot_rows_and_90_percent():
    rows = [_row(i, "agree" if i < 2 else "", spot="1" if i < 2 else "0") for i in range(10)]
    st = ap.sheet_status(rows)
    assert st["accepted_on_spotcheck"]
    assert ap.decide_row(rows[5], True) == ("CPP_OFF_BY_ONE", "model_prereview_spotchecked")
    rows[1]["human_verdict"], rows[1]["human_label"] = "disagree", "CPP_OTHER_ERROR"
    st = ap.sheet_status(rows)
    assert not st["accepted_on_spotcheck"]  # 1/2 agreement
    rows[2]["spotcheck"] = "1"
    assert not ap.sheet_status([_row(0, "agree", spot="1"), _row(1, "", spot="1")])["accepted_on_spotcheck"]


def test_human_rows_and_uncertain_model_rows():
    assert ap.decide_row(_row(0, "agree"), False) == ("CPP_OFF_BY_ONE", "human")
    assert ap.decide_row(_row(0, "disagree", "CPP_OTHER_ERROR"), False) == ("CPP_OTHER_ERROR", "human")
    assert ap.decide_row(_row(0, "unsure"), True) == (None, None)
    # a model 'uncertain' item is never accepted on the model's word
    assert ap.decide_row(_row(0, model_verdict="uncertain"), True) == (None, None)
    with pytest.raises(ValueError):
        ap.decide_row(_row(0, "disagree", "NOT_A_CLASS"), False)


def test_gold_rows_need_a_person():
    gold = {"pgx-1"}
    assert ap.may_accept_on_spotcheck("weak_labels_progpedia.csv", "pg-1", True, gold)
    assert not ap.may_accept_on_spotcheck("weak_labels_progpedia.csv", "pgx-1", True, gold)  # dev/IID row
    assert not ap.may_accept_on_spotcheck("iid_test_progpedia.csv", "pg-2", True, gold)  # gold sheet
    assert not ap.may_accept_on_spotcheck("weak_labels_progpedia.csv", "pg-1", False, gold)


def test_mark_spotcheck_is_seeded_20_percent():
    a = [{} for _ in range(30)]
    b = [{} for _ in range(30)]
    mark_spotcheck(a, 7)
    mark_spotcheck(b, 7)
    assert [r["spotcheck"] for r in a] == [r["spotcheck"] for r in b]
    assert sum(r["spotcheck"] == "1" for r in a) == 6


def test_merge_applies_confirm_relabel_reject(tmp_path):
    rows = [{"row_id": "cs-1", "label": "CPP_OFF_BY_ONE", "label_source": "weak_rule", "label_confidence": 0.2},
            {"row_id": "cs-2", "label": "CPP_OFF_BY_ONE", "label_source": "weak_rule", "label_confidence": 0.2},
            {"row_id": "cs-3", "label": "CPP_LOOP_BOUNDARY", "label_source": "weak_rule", "label_confidence": 0.2},
            {"row_id": "cs-4", "label": "CPP_LOOP_BOUNDARY", "label_source": "weak_rule", "label_confidence": 0.2}]
    dec = [{"row_id": "cs-1", "action": "confirm", "label": "CPP_OFF_BY_ONE", "basis": "human"},
           {"row_id": "cs-2", "action": "reject", "label": "CPP_OFF_BY_ONE", "basis": "model_prereview_spotchecked"},
           {"row_id": "cs-3", "action": "relabel", "label": "CPP_OTHER_ERROR", "basis": "human"},
           {"row_id": "cs-9", "action": "confirm", "label": "X", "basis": "human"}]
    p = tmp_path / "label_review_decisions.jsonl"
    p.write_text("".join(json.dumps(d) + "\n" for d in dec))
    out, stats = apply_review_decisions(rows, p)
    by = {r["row_id"]: r for r in out}
    assert set(by) == {"cs-1", "cs-3", "cs-4"}
    assert by["cs-1"]["label_source"] == "human" and by["cs-1"]["label_confidence"] == 1.0
    assert by["cs-3"]["label"] == "CPP_OTHER_ERROR" and "CPP_LOOP_BOUNDARY" in by["cs-3"]["secondary_labels"]
    assert by["cs-4"]["label_source"] == "weak_rule"
    assert stats["unknown_row_ids"] == ["cs-9"]


def test_merge_refuses_model_relabel(tmp_path):
    p = tmp_path / "d.jsonl"
    p.write_text(json.dumps({"row_id": "cs-1", "action": "relabel", "label": "CPP_OTHER_ERROR",
                             "basis": "model_prereview_spotchecked"}) + "\n")
    with pytest.raises(ValueError):
        apply_review_decisions([{"row_id": "cs-1", "label": "CPP_OFF_BY_ONE"}], p)


def test_no_decision_file_is_a_noop(tmp_path):
    rows = [{"row_id": "cs-1", "label": "CPP_OFF_BY_ONE"}]
    out, stats = apply_review_decisions(rows, tmp_path / "missing.jsonl")
    assert out == rows and stats["file"] is None
