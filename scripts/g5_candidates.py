"""Candidate problems for the confirmatory set (Gate 5, task U5 steps 1-3).

    python scripts/g5_candidates.py --raw-root G:/TraceLearn/Datasets_RAW

Every problem already used by the project is excluded, by id, from four places: the label and
lane files, the split files, the CodeNet reference solutions in `build_codenet_pool.py`, and any
cache or oracle-test file name. A problem is eligible when, in addition, its statement is in
English, has at least one sample, and its raw folder holds at least `--min-cpp` C++ submissions.
Eligible problems are put in a fixed order by a seeded shuffle. The team takes them in that order
(see `data/misconception_dataset/confirmatory/README.md`), so nobody chooses problems by the bugs
they contain.

What this reads: problem statements (HTML) and the NUMBER of files in each problem's `C++`
folder. It never opens a submission, a label, a feature or a prediction, so it does not expose
the confirmatory set. Only the 70 CodeNet problems whose submissions were copied locally are
candidates; every normalized CodeStream and PROGPedia problem is already used.

Writes `data/misconception_dataset/confirmatory/candidates_v1.csv`.
"""
from __future__ import annotations

import argparse
import csv
import glob
import html
import json
import os
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"
OUT = DS / "confirmatory" / "candidates_v1.csv"
CODENET = Path("Project_CodeNet") / "Project_CodeNet"
SEED = 20261122
MIN_CPP = 100
ENGLISH_SHARE = 0.9          # share of a statement's letters that are ASCII
FIELDS = ["rank", "problem_id", "eligible", "reason", "source", "atcoder_score", "title",
          "samples", "cpp_submissions", "english_share"]

_PID = re.compile(r"\bp\d{5}\b")


def codenet_id(problem_id: str | None) -> str | None:
    """`tl-codenet-p02594` or `p02594` -> `p02594`; anything else -> None."""
    text = problem_id or ""
    m = _PID.search(text)
    if not m:
        return None
    return m.group(0) if text == m.group(0) or "codenet" in text else None


def used_problem_ids(ds: Path = DS, root: Path = ROOT) -> dict[str, list[str]]:
    """CodeNet problem id -> where the project already used it."""
    used: dict[str, set[str]] = {}

    def add(pid: str | None, where: str) -> None:
        cid = codenet_id(pid)
        if cid:
            used.setdefault(cid, set()).add(where)

    for path in [ds / "annotations" / "labels.jsonl", *sorted((ds / "annotations").glob("tier*.jsonl"))]:
        if path.exists():
            for line in path.open(encoding="utf-8"):
                if line.strip():
                    add(json.loads(line).get("problem_id"), path.name)
    for path in sorted((ds / "splits").glob("*.csv")):
        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        for r in rows:
            add(r.get("problem_id"), path.name)
    pool = root / "scripts" / "build_codenet_pool.py"
    if pool.exists():
        for pid in re.findall(r"^def r_(p\d{5})\b", pool.read_text(encoding="utf-8"), re.M):
            add(pid, "build_codenet_pool.py reference")
    for base in (ds / "cache", ds / "oracle_tests"):
        for name in glob.glob(str(base / "**" / "*"), recursive=True):
            for pid in _PID.findall(os.path.basename(name)):
                add(pid, f"{base.name} file name")
    return {k: sorted(v) for k, v in used.items()}


def describe(statement_html: str) -> dict:
    """Facts about one statement: source, AtCoder score, title, sample count, English share."""
    parts = statement_html.split('<span class="lang-en">', 1)
    english = parts[1] if len(parts) > 1 else statement_html
    score = re.search(r"Score\s*:\s*<var>(\d+)</var>", english)
    # AtCoder pages carry a score line, with or without an English span; AOJ pages carry neither.
    atcoder = len(parts) > 1 or bool(score) or "配点" in statement_html
    title = re.search(r"<h1[^>]*>(.*?)</h1>", statement_html, re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", english))
    letters = [c for c in text if c.isalpha()]
    share = sum(c.isascii() for c in letters) / len(letters) if letters else 0.0
    return {
        "source": "AtCoder" if atcoder else "AOJ",
        "atcoder_score": int(score.group(1)) if score else None,
        "title": html.unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip() if title else "",
        "samples": len(re.findall(r"Sample Input", english, re.I)),
        "english_share": round(share, 2),
    }


def eligibility(pid: str, facts: dict | None, cpp: int, used: dict, min_cpp: int = MIN_CPP) -> tuple[bool, str]:
    """(eligible, reason). The rule is fixed here, before any program is opened."""
    if pid in used:
        return False, "used: " + "; ".join(used[pid])
    if facts is None:
        return False, "no statement"
    if facts["english_share"] < ENGLISH_SHARE:
        return False, f"statement not in English ({facts['english_share']} ASCII letters)"
    if facts["samples"] < 1:
        return False, "no sample in the statement"
    if cpp < min_cpp:
        return False, f"{cpp} C++ submissions (< {min_cpp})"
    return True, "eligible"


def order(eligible: list[str], seed: int = SEED) -> list[str]:
    """The fixed order the team works in: a seeded shuffle of the sorted ids."""
    ids = sorted(eligible)
    random.Random(seed).shuffle(ids)
    return ids


def build(raw_root: Path, seed: int = SEED, min_cpp: int = MIN_CPP) -> list[dict]:
    base = raw_root / CODENET
    used = used_problem_ids()
    rows = []
    for pid in sorted(os.listdir(base / "data")):
        cpp_dir = base / "data" / pid / "C++"
        cpp = len(os.listdir(cpp_dir)) if cpp_dir.is_dir() else 0      # a count of names; nothing is opened
        statement = base / "problem_descriptions" / f"{pid}.html"
        facts = describe(statement.read_text(encoding="utf-8", errors="ignore")) if statement.exists() else None
        ok, reason = eligibility(pid, facts, cpp, used, min_cpp)
        rows.append({"problem_id": pid, "eligible": ok, "reason": reason, "cpp_submissions": cpp,
                     **(facts or {"source": "", "atcoder_score": None, "title": "", "samples": 0, "english_share": None})})
    ranks = {pid: i + 1 for i, pid in enumerate(order([r["problem_id"] for r in rows if r["eligible"]], seed))}
    for r in rows:
        r["rank"] = ranks.get(r["problem_id"], "")
    rows.sort(key=lambda r: (r["rank"] == "", r["rank"] if r["rank"] != "" else 0, r["problem_id"]))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--raw-root", default=os.environ.get("TL_RAW_ROOT", "G:/TraceLearn/Datasets_RAW"))
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--min-cpp", type=int, default=MIN_CPP)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    rows = build(Path(a.raw_root), a.seed, a.min_cpp)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in FIELDS})
    n = sum(r["eligible"] for r in rows)
    print(f"{len(rows)} local CodeNet problems, {n} eligible, seed {a.seed} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
