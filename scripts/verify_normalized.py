"""Verify the normalized TraceLearn tables.

Checks parse, uniqueness, referential integrity, encoding, and that
JSONL and CSV row counts agree. Exits 1 on any failure.

Rules:
1. Read only. Change nothing.
2. Print one line per check with PASS or FAIL.
3. Exit 1 when any check fails.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "data" / "intermediate" / "normalized"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    """Print one check result and record a failure when it does not pass."""
    mark = "PASS" if ok else "FAIL"
    print(f"{label:<38} {mark}  {detail}")
    if not ok:
        failures.append(label)


def load(name: str) -> tuple[list[dict], int, int]:
    """Return rows, unparseable count and NUL-line count for one table."""
    rows: list[dict] = []
    bad = 0
    nul = 0
    path = BASE / name / f"{name}.jsonl"
    with path.open("rb") as fh:
        for raw in fh:
            if b"\x00" in raw:
                nul += 1
            try:
                rows.append(json.loads(raw.decode("utf-8")))
            except Exception:
                bad += 1
    return rows, bad, nul


def main() -> int:
    """Run every verification check."""
    problems, p_bad, p_nul = load("problems")
    subs, s_bad, s_nul = load("submissions")
    excl, e_bad, e_nul = load("exclusions")

    print("=== PARSE ===")
    check("problems parse", p_bad == 0, f"{len(problems)} rows, {p_bad} bad")
    check("submissions parse", s_bad == 0, f"{len(subs)} rows, {s_bad} bad")
    check("exclusions parse", e_bad == 0, f"{len(excl)} rows, {e_bad} bad")
    check("no NUL bytes", p_nul + s_nul + e_nul == 0,
          f"{p_nul + s_nul + e_nul} corrupted lines")

    print("\n=== UNIQUENESS ===")
    pids = [r["problem_id"] for r in problems]
    sids = [r["submission_id"] for r in subs]
    check("problem ids unique", len(set(pids)) == len(pids),
          f"{len(set(pids))} of {len(pids)}")
    check("submission ids unique", len(set(sids)) == len(sids),
          f"{len(set(sids))} of {len(sids)}")

    print("\n=== REFERENTIAL INTEGRITY ===")
    pset = set(pids)
    dangling = sum(1 for r in subs if r["problem_id"] not in pset)
    check("no dangling sub->problem", dangling == 0, f"{dangling} dangling")
    check("no null statements",
          sum(1 for r in problems if not r.get("statement_text")) == 0)
    check("no null code sha256",
          sum(1 for r in subs if not r.get("source_code_sha256")) == 0)
    check("no misconception labels set",
          sum(1 for r in subs if r.get("tracelearn_label")) == 0,
          "tracelearn_label must stay null")

    print("\n=== COUNTS ===")
    print("problems by source  :", dict(Counter(r["dataset_source"] for r in problems)))
    print("subs by source      :", dict(Counter(r["dataset_source"] for r in subs)))
    print("cpp submissions     :", sum(1 for r in subs if r["language"] == "cpp"))
    print("problems with tests :", sum(1 for r in problems if r["sample_test_count"] > 0))
    print("total sample tests  :", sum(r["sample_test_count"] for r in problems))
    print("student_ready       :", sum(1 for r in problems if r.get("student_ready")))
    print("with source label   :", sum(1 for r in subs if r["label_status"] == "source_label"))
    print("marked correct      :", sum(1 for r in subs if r["correct"] is True))

    print("\n=== EXCLUSIONS ===")
    for reason, n in sorted(Counter(r["exclusion_reason"] for r in excl).items()):
        print(f"  {reason:<24} {n}")
    check("exclusions reconcile",
          len(excl) == sum(Counter(r["exclusion_reason"] for r in excl).values()))

    print("\n=== CSV / JSONL AGREEMENT ===")
    for name, expect in (("problems", len(problems)),
                         ("submissions", len(subs)),
                         ("exclusions", len(excl))):
        csv_path = BASE / name / f"{name}.csv"
        with csv_path.open(encoding="utf-8-sig", newline="") as fh:
            n = sum(1 for _ in csv.DictReader(fh))
        check(f"{name} csv==jsonl", n == expect, f"csv={n} jsonl={expect}")

    print("\n=== RESULT ===")
    if failures:
        print(f"FAILED: {len(failures)} check(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
