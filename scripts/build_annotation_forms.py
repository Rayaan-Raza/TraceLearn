"""U5 — build the blind gold, dev-gold and calibration annotation forms (G6).

    python scripts/build_annotation_forms.py [--raw DIR] [--seed 20261021]

Reads the labeling index (annotations/codestream_failing_index.csv), the
execution cache and the raw submissions, and writes

  annotations/forms/calibration/        15 shared items (train-side), all raters
  annotations/forms/<rater>/            gold items for one rater (blind, shuffled)
  annotations/forms/<rater>/answers.csv the sheet the rater fills
  annotations/forms/dev_gold_<rater>/   60 natural-distribution items (dev-gold clusters), ~20 each
  annotations/forms_key/gold_key.csv    HIDDEN: item → row, stratum, firing_count, overlap,
                                        duplicate. Do not share with raters.
  reports/gold_forms_report.md

Design (Master Plan §9.0-G6, §13.4):
* 180 stratified + 40 uniform-random prevalence slice = 220 gold items, all
  from **test-side** clusters, spread over ≥12 clusters (≥10 under the
  <36-cluster fallback) and ≥30 users.
* Strata use the hidden LF/repair decision only to *select*; forms never
  show LF names, predictions or the stratum.
* 45 overlap items (hard-3 ×12 + one per remaining class) go to all four
  raters (3 team + external) → Fleiss κ. The remaining items are split
  across the three team raters. Each team rater also gets 10 blind
  duplicates of their own items (intra-rater check).
* Shortfalls (e.g. too few hard-3 candidates on the test side) are filled
  from the random slice and reported, never padded with train-side rows.

Note on the plan's "8 normal classes × 14": tl-cpp-v2 has 7 non-hard-3
misconception classes (1–7). To keep 180 stratified items we use 7 × 16 =
112, the same total.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from codestream_common import DATASET_DIR, find_raw, load_problems, load_submissions  # noqa: E402

ANN = DATASET_DIR / "annotations"
FORMS = ANN / "forms"
KEY = ANN / "forms_key"
EXEC_PATH = DATASET_DIR / "cache" / "codestream_exec.jsonl"
INDEX = ANN / "codestream_failing_index.csv"

NORMAL = ["CPP_LOOP_BOUNDARY", "CPP_OFF_BY_ONE", "CPP_ARRAY_BOUNDS", "CPP_UNINITIALIZED_VAR",
          "CPP_INT_OVERFLOW", "CPP_MISSING_BASE_CASE", "CPP_ASSIGN_VS_COMPARE"]
HARD3 = ["CPP_WRONG_LOOP_DIR", "CPP_RANGE_CHECK", "CPP_STALE_EXIT"]
OTHER = "CPP_OTHER_ERROR"
ALL_LABELS = NORMAL[:3] + ["CPP_UNINITIALIZED_VAR"] + NORMAL[4:] + HARD3 + [OTHER]
ALL_LABELS = list(dict.fromkeys(ALL_LABELS))
QUOTA = {**{c: 16 for c in NORMAL}, **{c: 18 for c in HARD3}, OTHER: 14}
RANDOM_SLICE = 40
DEV_GOLD = 60
CALIBRATION = 15
TEAM = ["rayaan", "eman", "umaima"]
EXTERNAL = "external"
DUPLICATES = 10

CLASS_TEXT = {
    "CPP_LOOP_BOUNDARY": "Loop-test comparison operator is the cause (<= vs <, < n+1)",
    "CPP_OFF_BY_ONE": "Index / count / initial-value arithmetic is off by one (operator correct)",
    "CPP_ARRAY_BOUNDS": "Out of bounds by more than one element, or undersized fixed array",
    "CPP_UNINITIALIZED_VAR": "A declared variable is used before it is set",
    "CPP_INT_OVERFLOW": "Overflow-prone arithmetic (int too small) causes the failure",
    "CPP_MISSING_BASE_CASE": "Recursion has no (reachable) base case",
    "CPP_ASSIGN_VS_COMPARE": "= used where == was meant, inside a condition",
    "CPP_WRONG_LOOP_DIR": "Iterates backwards / reversed where ascending order is required",
    "CPP_RANGE_CHECK": "Input validation rejects valid or accepts invalid values at a range edge",
    "CPP_STALE_EXIT": "Loop exit condition depends on a variable never updated in the loop",
    "CPP_OTHER_ERROR": "A different bug — none of the classes above explains the first failing test",
}


def stratum_of(r: dict) -> str | None:
    """Hidden selection stratum from the labeling decision."""
    if r["decision"] in ("repair_verified", "weak_rule", "discovery") and r["label"]:
        return r["label"]
    if r["decision"] == "discovery":
        fc = [c for c in r["fired_classes"].split("|") if c]
        return fc[0] if fc else None
    if r["decision"] == "no_fire":
        return OTHER
    return None  # multi_signal: only via the random slice


def pick_spread(cands: list[dict], k: int, rng: random.Random, taken: set) -> list[dict]:
    """Round-robin over clusters so a stratum does not come from one problem."""
    by_c = defaultdict(list)
    for r in cands:
        if r["row_id"] not in taken:
            by_c[r["problem_cluster"]].append(r)
    for v in by_c.values():
        rng.shuffle(v)
    order = sorted(by_c, key=lambda c: rng.random())
    out = []
    while len(out) < k and any(by_c.values()):
        for c in order:
            if by_c[c] and len(out) < k:
                out.append(by_c[c].pop())
    return out


def evidence_block(sub, prob, res: dict, max_tests: int = 3) -> dict:
    """What a rater sees: code, statement, failing tests with actual output,
    raw compiler warnings and sanitizer/Valgrind messages. No LF output."""
    t = res.get("tests") or {}
    fails = [x for x in t.get("results", []) if x.get("status") not in ("pass", "skipped")]
    shown = []
    for x in fails[:max_tests]:
        i = x["idx"]
        shown.append({"test": i + 1, "status": x["status"],
                      "input": prob.tests[i]["input"][:600],
                      "expected": prob.tests[i]["output"][:600],
                      "actual": (x.get("stdout_head") or "")[:600]})
    rt = res.get("runtime") or {}
    san = [{"tool": r["tool"], "kind": r["kind"], "line": r.get("line")}
           for r in ((rt.get("sanitizer") or {}).get("reports") or [])[:4]]
    vg = sorted(((rt.get("valgrind") or {}).get("kinds") or {}).keys())
    warns = [f"line {w['line']}: {w['message']}" for w in ((res.get("warnings") or {}).get("items") or [])[:8]]
    return {"language": sub.lang, "statement": prob.statement[:3000], "code": sub.code,
            "tests_passed": f"{t.get('passed')}/{t.get('total')}", "failing_tests": shown,
            "compiler_warnings": warns, "sanitizer": san, "valgrind": vg,
            "crashed": rt.get("any_crash"), "timed_out": rt.get("any_timeout")}


def render_html(title: str, items: list[tuple[str, dict]]) -> str:
    esc = html.escape
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)}</title>",
             "<style>body{font-family:system-ui,sans-serif;max-width:980px;margin:24px auto;padding:0 16px;color:#1d1d1f;background:#fff}"
             "pre{background:#f5f5f7;padding:10px;overflow-x:auto;font-size:13px;border-radius:6px}"
             ".item{border-top:2px solid #ccc;margin-top:32px;padding-top:12px}h2{font-size:18px}"
             "table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:4px 8px;vertical-align:top;font-size:13px}</style></head><body>",
             f"<h1>{esc(title)}</h1>",
             "<p>For each item pick the <b>primary</b> misconception — the one that explains the "
             "<b>first failing test</b> — and tick any secondary ones in <code>answers.csv</code>. "
             "If you cannot decide, answer <code>UNCERTAIN</code>. Do not look anything up in the pipeline.</p>",
             "<h3>Classes</h3><table>" + "".join(f"<tr><td><code>{c}</code></td><td>{esc(CLASS_TEXT[c])}</td></tr>"
                                                 for c in ALL_LABELS) + "</table>"]
    for item_id, ev in items:
        parts.append(f"<div class='item'><h2>{esc(item_id)} · {esc(ev['language'])} · tests passed {esc(ev['tests_passed'])}</h2>")
        parts.append(f"<details><summary>Problem statement</summary><pre>{esc(ev['statement'])}</pre></details>")
        parts.append(f"<pre>{esc(ev['code'])}</pre>")
        for ft in ev["failing_tests"]:
            parts.append(f"<p>Failing test {ft['test']} ({esc(ft['status'])})</p><table><tr><th>Input</th><th>Expected</th><th>Actual</th></tr>"
                         f"<tr><td><pre>{esc(ft['input'])}</pre></td><td><pre>{esc(ft['expected'])}</pre></td><td><pre>{esc(ft['actual'])}</pre></td></tr></table>")
        extra = []
        if ev["compiler_warnings"]:
            extra.append("Compiler: " + "; ".join(ev["compiler_warnings"]))
        if ev["sanitizer"]:
            extra.append("Sanitizer: " + "; ".join(f"{s['tool']} {s['kind']} line {s['line']}" for s in ev["sanitizer"]))
        if ev["valgrind"]:
            extra.append("Valgrind: " + ", ".join(ev["valgrind"]))
        if ev["crashed"]:
            extra.append("Crashed on at least one test")
        if ev["timed_out"]:
            extra.append("Timed out on at least one test")
        if extra:
            parts.append("<ul>" + "".join(f"<li>{esc(x)}</li>" for x in extra) + "</ul>")
        parts.append("</div>")
    parts.append("</body></html>")
    return "\n".join(parts)


def write_form(folder: Path, title: str, items: list[tuple[str, dict]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "form.html").write_text(render_html(title, items), encoding="utf-8")
    with open(folder / "items.jsonl", "w", encoding="utf-8") as f:
        for item_id, ev in items:
            f.write(json.dumps({"item_id": item_id, **ev}, ensure_ascii=False) + "\n")
    with open(folder / "answers.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["item_id", "primary_label", *[f"also_{c}" for c in ALL_LABELS], "notes"])
        for item_id, _ in items:
            w.writerow([item_id, "", *[""] * len(ALL_LABELS), ""])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=None)
    ap.add_argument("--seed", type=int, default=20261021)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    raw = find_raw(a.raw)
    probs = load_problems(raw)
    subs = {s.submission_id: s for s in load_submissions(raw)}
    execd = {}
    for line in EXEC_PATH.open(encoding="utf-8"):
        r = json.loads(line)
        execd[r["submission_id"]] = r["result"]
    with open(INDEX, encoding="utf-8") as f:
        index = list(csv.DictReader(f))
    for r in index:
        r["stratum"] = stratum_of(r)
    test_rows = [r for r in index if r["split_pool"] == "test"]
    dev_rows = [r for r in index if r["split_pool"] == "dev_gold"]
    train_rows = [r for r in index if r["split_pool"] == "train"]

    # ---- gold: stratified 180 + random 40 --------------------------------
    taken: set = set()
    gold = []  # (row, stratum_tag)
    shortfall = {}
    for cls, k in QUOTA.items():
        cands = [r for r in test_rows if r["stratum"] == cls]
        got = pick_spread(cands, k, rng, taken)
        for r in got:
            taken.add(r["row_id"])
            gold.append((r, cls))
        if len(got) < k:
            shortfall[cls] = k - len(got)
    need_random = RANDOM_SLICE + sum(shortfall.values())
    rest = [r for r in test_rows if r["row_id"] not in taken]
    rng.shuffle(rest)
    for r in rest[:need_random]:
        taken.add(r["row_id"])
        gold.append((r, "random"))

    # ---- overlap 45: hard-3 ×12 + one per remaining class -----------------
    overlap = []
    for cls in HARD3:
        overlap += [g for g in gold if g[1] == cls][:12]
    for cls in NORMAL + [OTHER]:
        overlap += [g for g in gold if g[1] == cls][:1]
    pool = [g for g in gold if g not in overlap]
    while len(overlap) < 45 and pool:
        overlap.append(pool.pop(rng.randrange(len(pool))))
    single = [g for g in gold if g not in overlap]
    rng.shuffle(single)

    # ---- assign, add duplicates, write --------------------------------------
    key_rows = []
    item_no = 0
    per_rater = {r: [] for r in TEAM + [EXTERNAL]}
    for i, g in enumerate(single):
        per_rater[TEAM[i % 3]].append((g, False, False))
    for g in overlap:
        for rater in TEAM + [EXTERNAL]:
            per_rater[rater].append((g, True, False))
    for rater in TEAM:
        own = [x for x in per_rater[rater] if not x[1]]
        for g, _, _ in rng.sample(own, min(DUPLICATES, len(own))):
            per_rater[rater].append((g, False, True))
    for rater, lst in per_rater.items():
        rng.shuffle(lst)
        items = []
        for (r, tag), is_overlap, is_dup in lst:
            item_no += 1
            item_id = f"G{item_no:04d}"
            s = subs[r["submission_id"]]
            items.append((item_id, evidence_block(s, probs[s.problem_id], execd[s.submission_id])))
            key_rows.append({"form": "gold", "rater": rater, "item_id": item_id, "row_id": r["row_id"],
                             "submission_id": r["submission_id"], "problem_cluster": r["problem_cluster"],
                             "user_id_hash": r["user_id_hash"], "stratum": tag,
                             "firing_count": r["firing_count"], "overlap": is_overlap,
                             "duplicate": is_dup, "lf_decision": r["decision"], "lf_label": r["label"]})
        write_form(FORMS / rater, f"TraceLearn gold annotation — {rater}", items)

    # ---- dev-gold: 60 natural-distribution items, ~20 per team rater ------
    dev = list(dev_rows)
    rng.shuffle(dev)
    dev = dev[:DEV_GOLD]
    for k, rater in enumerate(TEAM):
        items = []
        for r in dev[k::len(TEAM)]:
            item_no += 1
            item_id = f"D{item_no:04d}"
            s = subs[r["submission_id"]]
            items.append((item_id, evidence_block(s, probs[s.problem_id], execd[s.submission_id])))
            key_rows.append({"form": "dev_gold", "rater": rater, "item_id": item_id, "row_id": r["row_id"],
                             "submission_id": r["submission_id"], "problem_cluster": r["problem_cluster"],
                             "user_id_hash": r["user_id_hash"], "stratum": "natural",
                             "firing_count": r["firing_count"], "overlap": False, "duplicate": False,
                             "lf_decision": r["decision"], "lf_label": r["label"]})
        write_form(FORMS / f"dev_gold_{rater}", f"TraceLearn dev-gold annotation — {rater}", items)

    # ---- calibration: 15 train-side items across strata ---------------------
    cal = []
    cal_taken: set = set()
    for cls in ALL_LABELS:
        got = pick_spread([r for r in train_rows if r["stratum"] == cls], 1, rng, cal_taken)
        for r in got:
            cal_taken.add(r["row_id"])
            cal.append(r)
    rest = [r for r in train_rows if r["row_id"] not in cal_taken]
    rng.shuffle(rest)
    cal += rest[:max(0, CALIBRATION - len(cal))]
    cal = cal[:CALIBRATION]
    items = []
    for r in cal:
        item_no += 1
        item_id = f"C{item_no:04d}"
        s = subs[r["submission_id"]]
        items.append((item_id, evidence_block(s, probs[s.problem_id], execd[s.submission_id])))
        key_rows.append({"form": "calibration", "rater": "all", "item_id": item_id, "row_id": r["row_id"],
                         "submission_id": r["submission_id"], "problem_cluster": r["problem_cluster"],
                         "user_id_hash": r["user_id_hash"], "stratum": r["stratum"] or "multi",
                         "firing_count": r["firing_count"], "overlap": True, "duplicate": False,
                         "lf_decision": r["decision"], "lf_label": r["label"]})
    write_form(FORMS / "calibration", "TraceLearn calibration round (15 items, all raters)", items)

    KEY.mkdir(parents=True, exist_ok=True)
    with open(KEY / "gold_key.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(key_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(key_rows)
    (KEY / "README.md").write_text(
        "# Hidden answer key\n\nMaps form items to rows, strata and LF decisions. "
        "Raters must not open this folder before adjudication.\n", encoding="utf-8")

    # ---- report ------------------------------------------------------------
    gold_rows = [g[0] for g in gold]
    clusters = {r["problem_cluster"] for r in gold_rows}
    users = {r["user_id_hash"] for r in gold_rows}
    strata = Counter(g[1] for g in gold)
    fcs = Counter(min(int(r["firing_count"]), 2) for r in gold_rows)
    test_clusters = {r["problem_cluster"] for r in test_rows}
    L = ["# Gold forms report (U5 → G6)", "",
         "Generated by `scripts/build_annotation_forms.py`. Do not edit by hand.", "",
         f"- Gold items: {len(gold)} (commitment 220, floor 150) from {len(test_rows)} failing test-side rows",
         f"- Clusters spanned: {len(clusters)} of {len(test_clusters)} test clusters · users: {len(users)} (need ≥30)",
         f"- Overlap items (4 raters): {len(overlap)} · duplicates per team rater: {DUPLICATES}",
         f"- Items per rater: " + ", ".join(f"{k} {len(v)}" for k, v in per_rater.items()),
         f"- Dev-gold: {len(dev)} natural-distribution items from {len({r['problem_cluster'] for r in dev})} dev-gold clusters",
         f"- Calibration: {len(cal)} train-side items", "",
         "## Strata (selection only — hidden from raters)", "", "| Stratum | Quota | Selected | Shortfall |",
         "|---|---:|---:|---:|"]
    for cls, k in QUOTA.items():
        L.append(f"| {cls} | {k} | {strata[cls]} | {shortfall.get(cls, 0)} |")
    L.append(f"| random slice | {RANDOM_SLICE} | {strata['random']} | — |")
    L += ["", f"Shortfalls are filled from the uniform random slice (it absorbed {sum(shortfall.values())} extra items). "
          "A class whose stratum is short still counts any random-slice item adjudicated to it.", "",
          f"- firing_count over gold: 0 → {fcs[0]}, 1 → {fcs[1]}, 2+ → {fcs[2]}", "",
          "## Rater workflow", "",
          "1. Everyone does `forms/calibration/` together, discusses, and writes the decision tree into `ANNOTATION_GUIDELINE.md`.",
          "2. Each rater fills `forms/<rater>/answers.csv` from `forms/<rater>/form.html`.",
          "3. Run `scripts/adjudicate_gold.py` → Fleiss κ (4 raters, overlap), intra-rater agreement, majority labels → `annotations/gold.jsonl`."]
    rep = DATASET_DIR / "reports" / "gold_forms_report.md"
    rep.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
