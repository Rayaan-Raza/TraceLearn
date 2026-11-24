"""S1 of docs/WEAK_CLASS_STRATEGY.md: a blind review of the OTHER_ERROR rows the guideline's own test disputes.

    python scripts/build_fixfirst_review.py [--raw-root G:/TraceLearn/Datasets_RAW] [--out DIR]

Selects every real, training-side row (train and dev-gold; never the held-out split) labelled
OTHER_ERROR where exactly one class's single edit makes the first failing test pass
(`repair.<class>_fix_first == 1`, the check in ANNOTATION_GUIDELINE.md section 2). Mixes in control
rows so a rater cannot tell a disputed row from any other: OTHER_ERROR rows with no such edit, and
rows already labelled with the class whose edit passes. Writes to
`review/fixfirst_conflicts/`:

- `blind_sheet.csv`  pass 1, for raters: locator, problem, first failing test (input, expected
  and actual output when available) and blank answer columns. No current label, no edit,
  no model output, as in the U4 blind sheets.
- `evidence.md`      pass 2, for adjudication after pass 1 only: each row's fixing edit, its test
  gains and, with `--raw-root`, the code and the candidate edits of that kind as diffs.
- `key.csv`          the group of each item and the recorded label. Not for raters.
- `README.md`        instructions for raters, without the purpose or the group sizes.
- `COORDINATOR.md`   group sizes and how decisions are recorded. Not for raters.

Raters must not open evidence.md or key.csv before their pass-1 answers are submitted.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import gzip
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DS = ROOT / "data" / "misconception_dataset"
OUT = DS / "review" / "fixfirst_conflicts"
# With --raw-root the output holds program text that may not be redistributed (DATASET_CARD.md), so it goes
# to the git-ignored cache and never to a tracked folder.
RAW_OUT = DS / "cache" / "fixfirst_review"
CACHE = DS / "cache" / "counterfactual" / "evidence.jsonl"
OTHER = "CPP_OTHER_ERROR"
# The classes whose first-set repair the cache measures with fix_first.
FIX_CLASSES = ("LOOP_BOUNDARY", "OFF_BY_ONE", "ARRAY_BOUNDS", "UNINITIALIZED_VAR", "INT_OVERFLOW",
               "RANGE_CHECK", "ASSIGN_VS_COMPARE", "STALE_EXIT")
SEED = 20261124
N_CONTROL_OTHER = 20
N_CONTROL_CLASS = 15
CHOICES = ("OFF_BY_ONE | LOOP_BOUNDARY | ARRAY_BOUNDS | INT_OVERFLOW | UNINITIALIZED_VAR | RANGE_CHECK | "
           "ASSIGN_VS_COMPARE | STALE_EXIT | MISSING_BASE_CASE | WRONG_LOOP_DIR | OTHER_ERROR | UNCERTAIN")
TRUNC = 400


def _num(v: str) -> float:
    return float(v) if v not in ("", "nan", "NaN") else math.nan


def load_rows(ds: Path = DS) -> list[dict]:
    """Real train / dev-gold rows with their label, split and fix-first classes."""
    meta = {}
    for line in (ds / "annotations" / "labels.jsonl").open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            meta[r["row_id"]] = r
    with (ds / "splits" / "splits.csv").open(newline="", encoding="utf-8") as fh:
        split = {r["row_id"]: r["split"] for r in csv.DictReader(fh)}
    rows = []
    with (ds / "features" / "features.csv").open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            rid = rec["row_id"]
            m = meta[rid]
            if m["dataset_source"] == "SYNTHETIC" or split.get(rid) not in ("train", "dev_gold"):
                continue
            fixes = [c for c in FIX_CLASSES if _num(rec.get(f"repair.{c.lower()}_fix_first", "")) == 1]
            rows.append({"row_id": rid, "label": m["label"], "split": split[rid], "problem_id": m["problem_id"],
                         "source": m["dataset_source"], "label_status": m.get("label_status"),
                         "source_code_path": m.get("source_code_path") or m.get("source_record_id") or "",
                         "source_record_id": m.get("source_record_id"), "fix_first": fixes, "meta": m})
    return rows


def select(rows: list[dict], seed: int = SEED) -> list[dict]:
    """The disputed rows plus seeded controls, each tagged with its group; shuffled."""
    disputed = [dict(r, group="disputed", evidence_class=r["fix_first"][0]) for r in rows
                if r["label"] == OTHER and len(r["fix_first"]) == 1]
    classes = {r["evidence_class"] for r in disputed}
    rng = random.Random(seed)
    clean_other = [r for r in rows if r["label"] == OTHER and not r["fix_first"]]
    agreeing = [r for r in rows if r["label"] != OTHER and r["fix_first"] == [r["label"].removeprefix("CPP_")]
                and r["label"].removeprefix("CPP_") in classes]
    controls = ([dict(r, group="control_other", evidence_class="") for r in
                 rng.sample(sorted(clean_other, key=lambda r: r["row_id"]), min(N_CONTROL_OTHER, len(clean_other)))]
                + [dict(r, group="control_class", evidence_class=r["fix_first"][0]) for r in
                   rng.sample(sorted(agreeing, key=lambda r: r["row_id"]), min(N_CONTROL_CLASS, len(agreeing)))])
    items = sorted(disputed + controls, key=lambda r: r["row_id"])
    rng.shuffle(items)
    for i, r in enumerate(items, 1):
        r["item_id"] = f"FF-{i:03d}"
    return items


def _tests_offline(pid: str) -> list[dict] | None:
    """The problem's tests when they are in the repository (CodeNet, ProgPedia); None otherwise."""
    if pid.startswith("tl-codenet-"):
        path = DS / "oracle_tests" / "codenet" / f"{pid[len('tl-codenet-'):]}.json.gz"
        return json.load(gzip.open(path, "rt", encoding="utf-8")) if path.exists() else None
    if pid.startswith("tl-progpedia-"):
        return _progpedia_tests(pid)
    return None


def _progpedia_tests(pid: str) -> list[dict] | None:
    """`progpedia_oracle_tests.load_tests` without its sandbox import (Linux-only): stored inputs, or
    inputs regenerated from their seed and checked against the stored hash."""
    import hashlib

    import progpedia_generators as gen

    path = DS / "oracle_tests" / "progpedia" / f"{pid}.json.gz"
    if not path.exists():
        return None
    data = json.load(gzip.open(path, "rt", encoding="utf-8"))
    if not data.get("sample_check"):
        return None
    out = []
    for t in data["tests"]:
        inp = t["input"]
        if inp is None:
            inp = gen.generate(pid, t["kind"], random.Random(t["gen_seed"]))
            if hashlib.sha256(inp.encode()).hexdigest() != t["input_sha256"]:
                return None   # the generator changed: better no input than a wrong one
        out.append({"input": inp, "output": t["output"]})
    return out


def _cut(s: str | None) -> str:
    if s is None:
        return ""
    s = s.replace("\r\n", "\n")
    return s if len(s) <= TRUNC else s[:TRUNC] + f"... [{len(s) - TRUNC} more chars]"


def evidence_of(rows: list[dict], cache: Path = CACHE) -> dict[str, dict]:
    want = {r["row_id"] for r in rows}
    out = {}
    with cache.open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r["row_id"] in want:
                out[r["row_id"]] = r
    return out


def first_failure(ev: dict | None) -> dict:
    """Index, actual output head and test counts of the first failing test, from the run record."""
    if not ev or not ev.get("tests"):
        return {}
    t = ev["tests"]
    idx = (ev.get("cf") or {}).get("first", t.get("first_failed"))
    res = next((x for x in t.get("results") or [] if x["idx"] == idx), {})
    return {"index": idx, "status": res.get("status"), "actual_head": res.get("stdout_head"),
            "passed": t.get("passed"), "total": t.get("total")}


def resolve_code(rows: list[dict], raw_root: Path) -> dict[str, str]:
    """Program text for each row, resolved the way the merge does. Empty when the raw copy is absent."""
    import merge_dataset as M

    index_csv = ROOT / "data" / "Data_from_Datasets" / "intermediate" / "normalized" / "submissions" / "submissions.csv"
    index = M.load_index(index_csv) if index_csv.exists() else {}
    if (DS / "annotations" / "codenet_index.csv").exists():
        index.update(M.load_index(DS / "annotations" / "codenet_index.csv"))
    metas = [r["meta"] for r in rows]
    ref = M.prefetch_csv_refs(metas, index, raw_root)
    out = {}
    for r in rows:
        rr = dict(r["meta"])
        rr["source_code_path"] = index.get(r.get("source_record_id") or "") or rr.get("source_code_path")
        try:
            code = M.resolve_code(rr, raw_root, ref_index=ref)
        except Exception:  # noqa: BLE001 - one unreadable file leaves that row without code
            code = None
        if code:
            out[r["row_id"]] = code
    return out


def candidate_diffs(code: str, cls: str, ops: list[str]) -> list[str]:
    """Unified diffs of this class's candidate edits whose kind is one of `ops` (the kinds that passed)."""
    import repair_verify

    diffs = []
    for rep in repair_verify.candidates(code, f"CPP_{cls}"):
        if rep.op in ops:
            d = "".join(difflib.unified_diff(code.splitlines(True), rep.code.splitlines(True),
                                             "submitted", f"edit {rep.op}", n=1))
            if d and d not in diffs:
                diffs.append(d)
    return diffs[:6]


def build(out: Path = OUT, raw_root: Path | None = None, ds: Path = DS) -> dict:
    if raw_root and DS / "cache" not in out.resolve().parents:
        raise ValueError(f"--raw-root output must stay under {DS / 'cache'}: raw programs are not redistributable")
    rows = load_rows(ds)
    items = select(rows)
    ev = evidence_of(items)
    codes = resolve_code(items, raw_root) if raw_root else {}
    tests_cache: dict[str, list[dict] | None] = {}
    with_input = 0
    if raw_root:
        from codestream_common import load_problems
        for r_id, prob in load_problems(raw_root).items():
            tests_cache[r_id if r_id.startswith("tl-") else f"tl-codestream-{r_id}"] = prob.tests or None
    # Raters get their own folder, so it can be handed over without the key and the evidence.
    rater, coord = (out / "rater", out / "coordinator") if raw_root else (out, out)
    for folder in (rater, coord):
        folder.mkdir(parents=True, exist_ok=True)
    if raw_root:
        (rater / "programs").mkdir(exist_ok=True)
        for r in items:
            if r["row_id"] in codes:
                ext = "c" if r["meta"].get("language") == "c" else "cpp"
                r["program"] = f"programs/{r['item_id']}.{ext}"
                (rater / r["program"]).write_text(codes[r["row_id"]], encoding="utf-8", newline="")
    out.mkdir(parents=True, exist_ok=True)

    blind_fields = ["item_id", "row_id", "problem_id", "source_code_path", "first_failing_test",
                    "first_failing_input", "expected_output", "actual_output_head",
                    "rater_label", "cause_line", "rater", "note"]
    with (rater / "blind_sheet.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=blind_fields, lineterminator="\n")
        w.writeheader()
        for r in items:
            ff = first_failure(ev.get(r["row_id"]))
            pid = r["problem_id"]
            if pid not in tests_cache:
                tests_cache[pid] = _tests_offline(pid)
            tests = tests_cache[pid]
            test = tests[ff["index"]] if tests and ff.get("index") is not None and ff["index"] < len(tests) else None
            with_input += test is not None
            w.writerow({"item_id": r["item_id"], "row_id": r["row_id"], "problem_id": pid,
                        "source_code_path": r.get("program") or r["source_code_path"],
                        "first_failing_test": "" if ff.get("index") is None else
                        f"#{ff['index']} ({ff.get('passed')}/{ff.get('total')} tests pass)",
                        "first_failing_input": _cut(test["input"]) if test else "(needs the raw copy)",
                        "expected_output": _cut(test["output"]) if test else "(needs the raw copy)",
                        "actual_output_head": _cut(ff.get("actual_head")),
                        "rater_label": "", "cause_line": "", "rater": "", "note": ""})

    with (coord / "key.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["item_id", "row_id", "group", "recorded_label", "label_status",
                                           "evidence_class", "split"], lineterminator="\n")
        w.writeheader()
        for r in sorted(items, key=lambda r: r["item_id"]):
            w.writerow({"item_id": r["item_id"], "row_id": r["row_id"], "group": r["group"],
                        "recorded_label": r["label"], "label_status": r["label_status"],
                        "evidence_class": r["evidence_class"], "split": r["split"]})

    lines = ["# Fix-first evidence (pass 2: adjudication only)", "",
             "Open this only after every rater has submitted pass 1. For each item: the class whose single edit "
             "makes the first failing test pass, the kinds of edit that did, and how many more tests then pass.",
             ""]
    n_diffs = 0
    for r in sorted(items, key=lambda r: r["item_id"]):
        e = ev.get(r["row_id"]) or {}
        lines.append(f"## {r['item_id']} `{r['row_id']}`  ({r['problem_id']})")
        lines.append("")
        if not r["evidence_class"]:
            lines += ["No class's single edit passes the first failing test.", ""]
            continue
        rec = ((e.get("cf") or {}).get("classes") or {}).get(f"CPP_{r['evidence_class']}") or {}
        ops = list(rec.get("ops") or [])
        lines.append(f"- Edit that passes the first failing test: **{r['evidence_class']}** "
                     f"({', '.join(ops) or 'kind not recorded'})")
        lines.append(f"- Candidate edits tried {rec.get('n')}, compiled {rec.get('compiled')}, passing the first "
                     f"failing test {rec.get('fix_first')}, without breaking a passing test {rec.get('fix_first_noreg')}, "
                     f"passing every test {rec.get('fix_all')}; best gain {rec.get('best_gain')} of the tests")
        code = codes.get(r["row_id"])
        if code and ops:
            diffs = candidate_diffs(code, r["evidence_class"], ops)
            n_diffs += bool(diffs)
            for d in diffs:
                lines += ["", "```diff", d.rstrip("\n"), "```"]
        elif not code:
            lines.append("- Code and diffs: run with `--raw-root` to embed them.")
        lines.append("")
    (coord / "evidence.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    groups = Counter(r["group"] for r in items)
    by_class = Counter(r["evidence_class"] for r in items if r["group"] == "disputed")
    where = "in this folder" if raw_root else "in the raw copy (Datasets_RAW)"
    readme = f"""# Label review: instructions for raters

{len(items)} real student programs. Fill a copy of `blind_sheet.csv` alone and save it as
`rater_<name>.csv`. Open each program at `source_code_path` {where}.

- `rater_label`: one of {CHOICES}. ANNOTATION_GUIDELINE.md section 2: the misconception that **causes**
  the first failing test.
- `cause_line`: the line you would change. `note`: required for OTHER_ERROR and UNCERTAIN.
- Before submitting, do not open any other file in this folder, the labels file, the strategy
  document, the pull request that added this sheet, or model output.
"""
    coordinator = f"""# Coordinator notes (not for raters)

Groups: {dict(groups)}. Classes of the edit in the disputed group: {dict(by_class)}. The disputed rows
are most of the sheet, so controls only partly hide which rows they are. Anyone who has read
docs/WEAK_CLASS_STRATEGY.md or the pull request is not a blind rater.

After every rater has submitted, adjudicate with `evidence.md` and `key.csv`. An edit that breaks
passing tests is weak evidence. Report agreement on the controls too. Record decisions in
`annotations/label_review_decisions.jsonl` (action `relabel` or `confirm`, basis `human`, item_id,
signed_off_by, note); never edit labels in place.
"""
    (coord / "COORDINATOR.md").write_text(coordinator, encoding="utf-8", newline="\n")
    (rater / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    return {"items": len(items), "groups": dict(groups), "disputed_by_class": dict(by_class),
            "with_test_input": with_input, "code_embedded": len(codes), "rows_with_diffs": n_diffs}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw-root", type=Path, default=None, help="Datasets_RAW, to embed code and diffs in evidence.md")
    ap.add_argument("--out", type=Path, default=None,
                    help="default: the tracked review folder, or the git-ignored cache with --raw-root")
    a = ap.parse_args(argv)
    if a.raw_root and not a.raw_root.is_dir():
        print(f"raw root not found: {a.raw_root}")
        return 2
    print(json.dumps(build(a.out or (RAW_OUT if a.raw_root else OUT), a.raw_root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
