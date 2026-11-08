"""Calibration round analysis: per-rater answers, κ, items to discuss, discussion sheet."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import calibration_round as cr  # noqa: E402
from build_annotation_forms import ALL_LABELS, write_answers  # noqa: E402

A, B, C = "CPP_OFF_BY_ONE", "CPP_LOOP_BOUNDARY", "CPP_ARRAY_BOUNDS"


def _fill(path: Path, labels: dict[str, str]) -> None:
    write_answers(path, list(labels))
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    for r in rows:
        r["primary_label"] = labels[r["item_id"]]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _answers(tmp_path: Path) -> Path:
    d = tmp_path / "calibration"
    d.mkdir()
    _fill(d / "answers_umaima.csv", {"C1": A, "C2": B, "C3": C})
    _fill(d / "answers_eman.csv", {"C1": A, "C2": A, "C3": C})
    _fill(d / "answers_rayaan.csv", {"C1": A, "C2": B, "C3": C})
    write_answers(d / "answers_external.csv", ["C1", "C2", "C3"])  # not started: ignored
    return d


def test_answer_sheet_has_every_label_column(tmp_path):
    write_answers(tmp_path / "a.csv", ["C1"])
    header = next(csv.reader(open(tmp_path / "a.csv", encoding="utf-8")))
    assert header == ["item_id", "primary_label", *[f"also_{c}" for c in ALL_LABELS], "notes"]


def test_analysis_flags_disagreements_and_confused_pairs(tmp_path):
    res = cr.analyse(cr.read_rater_answers(_answers(tmp_path)))
    assert res["raters"] == ["eman", "rayaan", "umaima"]  # empty external sheet does not count
    by = {it["item_id"]: it for it in res["per_item"]}
    assert by["C1"]["unanimous"] and by["C3"]["unanimous"]
    assert not by["C2"]["unanimous"] and by["C2"]["majority"] == B and by["C2"]["agree"] == 2
    assert dict(res["confusions"]) == {tuple(sorted((A, B))): 1}
    assert res["fleiss"] is not None and res["fleiss"] < 1


def test_report_hides_the_key_unless_asked(tmp_path):
    res = cr.analyse(cr.read_rater_answers(_answers(tmp_path)))
    plain = cr.render_report(res)
    assert "Rule said" not in plain and "Fleiss" in plain
    keyed = cr.render_report(res, {"C2": {"lf_label": B}})
    assert "Rule said" in keyed


def test_discussion_sheet_keeps_group_decisions(tmp_path):
    res = cr.analyse(cr.read_rater_answers(_answers(tmp_path)))
    out = tmp_path / "discussion.csv"
    cr.write_discussion(res, out)
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    rows[1]["agreed_label"], rows[1]["decision_rule"] = B, "operator vs arithmetic: fix the operator only"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    cr.write_discussion(res, out)  # re-run after more answers arrive
    again = {r["item_id"]: r for r in csv.DictReader(open(out, encoding="utf-8"))}
    assert again["C2"]["agreed_label"] == B and again["C2"]["decision_rule"].startswith("operator")
    assert again["C2"]["label_eman"] == A


def test_no_answers_is_an_error(tmp_path):
    d = tmp_path / "calibration"
    d.mkdir()
    write_answers(d / "answers_umaima.csv", ["C1"])
    assert cr.main(["--cal-dir", str(d)]) == 1
