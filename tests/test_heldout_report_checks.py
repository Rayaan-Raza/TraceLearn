"""Independent checks on the committed held-out report (task E4).

`scripts/eval_heldout_rows.py report` writes `reports/heldout_predictions.json`, `heldout_eval.json`
and `heldout_eval.md` from per-run files. These checks read the committed predictions and confirm
that the figures follow from the rows, so the report cannot go stale or drift from its own data
without CI failing. They do not import the evaluator.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
REPORTS = DS / "reports"
OTHER = "CPP_OTHER_ERROR"
ABSTAIN = "ABSTAIN"
PROBLEM_39 = "tl-progpedia-00000039"
BASELINE = "baseline: always OTHER_ERROR"
SCOPE_ALL = "All rows"
SCOPE_WITHOUT = f"Without {PROBLEM_39}"
SYSTEMS = ["audited: classifier only", "audited: full runtime", "pr17: classifier only", "pr17: full runtime"]


# ----------------------------------------------------------------- loading

@pytest.fixture(scope="module")
def predictions() -> dict:
    return json.loads((REPORTS / "heldout_predictions.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report() -> dict:
    return json.loads((REPORTS / "heldout_eval.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def markdown() -> str:
    return (REPORTS / "heldout_eval.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def runs() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((REPORTS / "heldout_runs").glob("*.json"))}


@pytest.fixture(scope="module")
def table(predictions) -> list[dict]:
    """Report rows as dicts: row_id, source, truth, problem, and one label per system."""
    cols = predictions["columns"]
    return [dict(zip(cols, row)) for row in predictions["rows"]]


@pytest.fixture(scope="module")
def splits() -> list[dict]:
    with (DS / "splits" / "splits.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _scope(rows: list[dict], scope: str) -> list[dict]:
    return rows if scope == SCOPE_ALL else [r for r in rows if r["problem"] != PROBLEM_39]


def _measures(rows: list[dict], system: str) -> dict:
    """Named precision, named recall, false alarm, abstain and accuracy, as counts."""
    label = (lambda r: OTHER) if system == BASELINE else (lambda r: r[system])
    named_truth = [r for r in rows if r["truth"] != OTHER]
    other_truth = [r for r in rows if r["truth"] == OTHER]
    flagged = [r for r in rows if label(r) not in (OTHER, ABSTAIN)]
    correct_named = sum(1 for r in flagged if label(r) == r["truth"])
    return {
        "precision": (correct_named, len(flagged)),
        "recall": (correct_named, len(named_truth)),
        "false_alarm": (sum(1 for r in other_truth if label(r) not in (OTHER, ABSTAIN)), len(other_truth)),
        "abstain": (sum(1 for r in rows if label(r) == ABSTAIN), len(rows)),
        "accuracy": (sum(1 for r in rows if label(r) == r["truth"]), len(rows)),
        "correct": sum(1 for r in rows if label(r) == r["truth"]),
        "wrong": sum(1 for r in rows if label(r) not in (r["truth"], ABSTAIN)),
    }


def _sha256_lf(path: Path) -> str:
    """SHA-256 with CRLF read as LF, so a Windows checkout agrees with git."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


# ----------------------------------------------------------------- 1. same rows

def test_every_system_scored_the_same_rows(predictions, table, runs):
    ids = [r["row_id"] for r in table]
    assert len(ids) == len(set(ids)), "a row id appears twice"
    for key, detail in predictions["detail"].items():
        assert [d["row_id"] for d in detail] == ids, f"{key} has different rows or a different order"
    for r in table:
        for system in SYSTEMS:
            assert r[system], f"{system} has no label for {r['row_id']}"
    shared = set.intersection(*[{x["row_id"] for x in run["rows"]} for run in runs.values()])
    assert set(ids) == shared, "the report is not the rows every run shares"


# ----------------------------------------------------------------- 2. counts add up

@pytest.mark.parametrize("system", SYSTEMS + [BASELINE])
def test_correct_wrong_and_abstained_add_up(table, system):
    m = _measures(table, system)
    assert m["correct"] + m["wrong"] + m["abstain"][0] == len(table)


@pytest.mark.parametrize("scope", [SCOPE_ALL, SCOPE_WITHOUT])
def test_per_problem_counts_sum_to_the_overall_counts(report, scope):
    block = report["scopes"][scope]
    per_problem = block["per_problem"]
    assert sum(p["rows"] for p in per_problem.values()) == block["n"]
    assert len(per_problem) == block["problems"]
    for system in SYSTEMS + [BASELINE]:
        overall = block["systems"][system]
        flagged = sum(p["systems"][system]["flagged"] for p in per_problem.values())
        correct = sum(p["systems"][system]["correct_named"] for p in per_problem.values())
        assert flagged == overall["precision_when_flagged"]["n"], system
        assert correct == overall["misconception_recall"]["k"], system


# ----------------------------------------------------------------- 3. recompute the figures

def _md_section(markdown: str, scope: str) -> str:
    start = markdown.index(f"## {scope}")
    nxt = markdown.find("\n## ", start + 3)
    return markdown[start: nxt if nxt != -1 else len(markdown)]


def _md_row(section: str, system: str) -> list[str]:
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == system:
            return cells
    raise AssertionError(f"no row for {system!r}")


def _md_ratio(cell: str) -> tuple[float | None, int, int]:
    found = re.fullmatch(r"(None|[0-9.]+) \[[^\]]*\] \((\d+)/(\d+)\)", cell)
    assert found, f"cannot read {cell!r}"
    value = None if found.group(1) == "None" else float(found.group(1))
    return value, int(found.group(2)), int(found.group(3))


@pytest.mark.parametrize("scope", [SCOPE_ALL, SCOPE_WITHOUT])
@pytest.mark.parametrize("system", SYSTEMS + [BASELINE])
def test_figures_in_the_report_follow_from_the_rows(table, markdown, report, scope, system):
    rows = _scope(table, scope)
    mine = _measures(rows, system)
    cells = _md_row(_md_section(markdown, scope), system)
    # cells: system, problem-weighted F1, macro-F1, precision, recall, false alarm, abstain, accuracy
    for name, cell in (("precision", cells[3]), ("recall", cells[4]), ("false_alarm", cells[5]), ("abstain", cells[6])):
        value, k, n = _md_ratio(cell)
        assert (k, n) == mine[name], f"{system} {name}: report says {k}/{n}, rows give {mine[name]}"
        assert value == (round(k / n, 3) if n else None), f"{system} {name}: {value} is not {k}/{n} to three decimals"
    k, n = mine["accuracy"]
    assert float(cells[7]) == round(k / n, 3)
    # the JSON report agrees with the markdown
    block = report["scopes"][scope]["systems"][system]
    assert block["precision_when_flagged"]["k"] == mine["precision"][0]
    assert block["precision_when_flagged"]["n"] == mine["precision"][1]


# ----------------------------------------------------------------- 4. known answer

def _named_counts(rows: list[dict]) -> tuple[int, int, int]:
    named_truth = [r for r in rows if r["truth"] != OTHER]
    flagged = [r for r in rows if r["classifier"]["label"] not in (OTHER, ABSTAIN)]
    return sum(1 for r in flagged if r["classifier"]["label"] == r["truth"]), len(flagged), len(named_truth)


def test_known_answer_for_the_audited_model(runs):
    """The supervisor's own figures: 75/104 and 75/204 on 664 rows; 17/37 and 17/92 without problem 39."""
    rows = runs["audited"]["rows"]
    assert len(rows) == 664
    assert _named_counts(rows) == (75, 104, 204)
    assert _named_counts([r for r in rows if r["problem"] != PROBLEM_39]) == (17, 37, 92)


# ----------------------------------------------------------------- 5. exclusion works

def test_tables_without_problem_39_hold_no_row_of_that_problem(table, report, markdown):
    block = report["scopes"][SCOPE_WITHOUT]
    assert PROBLEM_39 not in block["per_problem"]
    kept = [r for r in table if r["problem"] != PROBLEM_39]
    assert block["n"] == len(kept)
    assert block["problems"] == len({r["problem"] for r in kept})
    assert PROBLEM_39 in report["scopes"][SCOPE_ALL]["per_problem"], "the full table should still show it"
    assert f"## {SCOPE_WITHOUT} ({len(kept)} rows" in markdown


# ----------------------------------------------------------------- 6. no leakage

def test_no_scored_row_or_problem_was_trained_on(table, splits):
    trained = [s for s in splits if s["split"] in ("train", "dev_gold")]
    scored_ids = {r["row_id"] for r in table}
    assert not scored_ids & {s["row_id"] for s in trained}, "a scored row is in train or dev_gold"
    by_id = {s["row_id"]: s for s in splits}
    assert scored_ids <= set(by_id), "a scored row has no split"
    assert {by_id[i]["split"] for i in scored_ids} <= {"test", "test_iid"}
    scored_problems = {r["problem"] for r in table}
    assert not scored_problems & {s["problem_id"] for s in trained}, "a scored problem appears in training"
    assert not {by_id[i]["cluster_id"] for i in scored_ids} & {s["cluster_id"] for s in trained}, \
        "a scored row shares a cluster with a training row"


# ----------------------------------------------------------------- 7. model matches

def test_model_hash_in_the_header_is_the_committed_model(report, runs, markdown):
    """The run the report calls served is the committed model (it was `audited` until Gate 4)."""
    digest = _sha256_lf(DS / "models" / "xgb_execution_v1.json")
    served = report["served_system"].split(":")[0]
    assert report["models"][served]["sha256_16"] == digest[:16]
    assert runs[served]["run"]["model_sha256"] == digest
    assert f"`{digest[:16]}`" in markdown


# ----------------------------------------------------------------- 8. provenance adds up

def test_label_origin_counts_sum_to_the_row_count(table, report, runs):
    counts = report["label_provenance"]
    assert sum(counts.values()) == report["n_rows"] == len(table)
    by_id = {r["row_id"]: r for r in runs["audited"]["rows"]}
    recount = Counter(f"{by_id[r['row_id']]['label_source']}/{by_id[r['row_id']]['label_status'] or 'none'}" for r in table)
    assert dict(recount) == counts
