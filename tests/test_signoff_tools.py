"""Blind sign-off page builder and the importer for signed sheets."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_signoff_pages as bp  # noqa: E402
import import_signoff as imp  # noqa: E402
from prereview_common import COLUMNS, write_sheet  # noqa: E402


def _row(i, spot="0", **kw):
    r = {c: "" for c in COLUMNS}
    r.update(item_id=f"X-{i:03d}", row_id=f"pg-{i}", dataset_source="PROGPEDIA", spotcheck=spot,
             model_verdict="correct", model_label="CPP_ARRAY_BOUNDS", current_label="CPP_ARRAY_BOUNDS")
    r.update(kw)
    return r


def test_rows_to_sign_weak_sheet_spotcheck_plus_gold():
    rows = [_row(1, "1"), _row(2), _row(3)]
    picked = bp.rows_to_sign("weak_labels_progpedia", rows, gold={"pg-3"})
    assert [r["item_id"] for r in picked] == ["X-001", "X-003"]
    assert len(bp.rows_to_sign("weak_labels_progpedia", rows, set(), all_rows=True)) == 3


def test_rows_to_sign_gold_sheet_is_every_row():
    rows = [_row(1), _row(2)]
    assert len(bp.rows_to_sign("iid_test_progpedia", rows, gold=set())) == 2
    assert len(bp.rows_to_sign("dev_gold_codestream", rows, gold=set())) == 2


def test_label_hints_are_split_from_observations():
    ev = {"lf": "pg-3", "verdict": "RUNTIME_ERROR",
          "exec": {"oracle_tests_passed": "0/12", "exec_label": "CPP_ARRAY_BOUNDS", "repair": None,
                   "sanitizer": {"asan:global-buffer-overflow": 1}}}
    obs, hints = bp.split_evidence(ev)
    assert set(hints) == {"lf", "exec.exec_label", "exec.repair"}
    assert obs["exec.sanitizer"] == {"asan:global-buffer-overflow": 1}
    assert "verdict" in obs and "exec.oracle_tests_passed" in obs


def test_page_escapes_script_end_tags():
    page = bp.render_page({"x": "</script><script>alert(1)</script>"})
    assert page.count("</script>") == 2  # the page's own two script blocks only


def _signed(r, verdict="agree", label="", by="Umaima Zeeshan"):
    return dict(r, human_verdict=verdict, human_label=label, signed_off_by=by, signed_off_at="2026-11-08")


def test_merge_copies_human_columns_only():
    repo = [_row(1, "1"), _row(2)]
    signed = [_signed(repo[0]), dict(repo[1])]
    out, n_new = imp.merge_sheet(repo, signed)
    assert n_new == 1 and out[0]["human_verdict"] == "agree" and out[1]["human_verdict"] == ""


@pytest.mark.parametrize("mutate, msg", [
    (lambda rows: rows[0].update(model_label="CPP_OFF_BY_ONE"), "non-human column"),
    (lambda rows: rows.reverse(), "order differ"),
    (lambda rows: rows[0].update(human_verdict="disagree", human_label="NOPE", signed_off_by="U"), "human_label"),
    (lambda rows: rows[0].update(human_verdict="agree", signed_off_by=""), "signed_off_by"),
    (lambda rows: rows[0].update(human_verdict="maybe", signed_off_by="U"), "agree / disagree / unsure"),
])
def test_merge_refuses_bad_exports(mutate, msg):
    repo = [_row(1, "1"), _row(2)]
    signed = [dict(r) for r in repo]
    mutate(signed)
    with pytest.raises(imp.ImportRefused, match=msg):
        imp.merge_sheet(repo, signed)


def test_merge_never_overwrites_a_different_signature():
    repo = [_signed(_row(1, "1"), "agree", by="Rater A"), _row(2)]
    same = [dict(repo[0]), dict(repo[1])]
    assert imp.merge_sheet(repo, same)[1] == 0  # identical re-sign is fine
    other = [_signed(_row(1, "1"), "disagree", "CPP_OFF_BY_ONE", by="Rater B"), dict(repo[1])]
    with pytest.raises(imp.ImportRefused, match="already signed"):
        imp.merge_sheet(repo, other)


def test_import_cli_writes_the_sheet(tmp_path):
    sheet_dir = tmp_path / "sheets"
    repo = [_row(1, "1"), _row(2)]
    write_sheet(sheet_dir / "weak_labels_x.csv", repo)
    export = tmp_path / "export" / "weak_labels_x.csv"
    write_sheet(export, [_signed(repo[0], "disagree", "CPP_OTHER_ERROR"), repo[1]])
    assert imp.main([str(export), "--sheet-dir", str(sheet_dir)]) == 0
    from prereview_common import read_sheet
    got = read_sheet(sheet_dir / "weak_labels_x.csv")
    assert got[0]["human_verdict"] == "disagree" and got[0]["human_label"] == "CPP_OTHER_ERROR"
    assert imp.main([str(tmp_path / "nope.csv"), "--sheet-dir", str(sheet_dir)]) == 1
