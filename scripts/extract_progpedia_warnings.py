#!/usr/bin/env python3
"""Extract gcc/g++ `-Wall` warnings for PROGpedia C/C++ submissions (pg-1/pg-4).

The compiler is the *other* half of the pg-1/pg-4 conjunctions (`-Wparentheses`,
`-Wmaybe-uninitialized`). Docker is unavailable, so WSL Ubuntu gcc/g++ 13.3.0 is
the available tooling (plan allows "warnings via available tooling"; a run that
cannot complete yields null warnings — never guessed, §6).

Design:
- Scope: PROGPEDIA rows with language in {c, cpp} (Java/Python have no gcc
  warnings; Java is out of the lane entirely, user directive).
- Jobs are unique per (compiler, sha256): identical submissions compile once.
- Work dir sidecars (`<compiler>-<sha>.err` / `.exit`) ARE the cache — reruns
  compile only unfinished jobs (resumable; 12 = GNU timeout exit -> flags null,
  partial stderr is never trusted).
- Output: features/progpedia_warnings.csv keyed by source_record_id,
  deterministic row order; `flags` holds parse_warnings() JSON (or null).

CLI:
    python scripts/extract_progpedia_warnings.py [--workers 12] [--raw-root ...]
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tracelearn_features.parsers import parse_warnings  # noqa: E402

DEFAULT_RAW_ROOT = Path(r"G:\TraceLearn\Datasets_RAW")
DEFAULT_INDEX = ROOT / "data/Data_from_Datasets/intermediate/normalized/submissions/submissions.csv"
DEFAULT_OUT = ROOT / "data/misconception_dataset/features/progpedia_warnings.csv"
DEFAULT_WORK = ROOT / "data/misconception_dataset/features/_warnings_work"

# language -> compiler; anything else is out of scope (pg rules lane).
COMPILERS: dict[str, str] = {"c": "gcc", "cpp": "g++"}
GNU_TIMEOUT_EXIT = 124
# Full codegen (-c -o /dev/null), NOT -fsyntax-only: the front-end-only pass
# silently drops every dataflow diagnostic (-Wuninitialized,
# -Wmaybe-uninitialized), measured 0 warnings under -fsyntax-only on cases
# where -c warns. Warm-cache cost ~0.15s/file (12 workers < 1 min batch).
COMPILE_FLAGS = ("-c", "-O2", "-Wall")
CSV_COLUMNS = ("source_record_id", "language", "compiler", "source_code_sha256",
               "compile_ok", "flags")

Runner = Callable[[list[dict[str, Any]], Path, int], None]


# ------------------------------------------------------------------ selection


def select_rows(index_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """PROGPEDIA x {c, cpp} — the pg lane's warning scope."""
    return [
        r for r in index_rows
        if r.get("dataset_source") == "PROGPEDIA" and r.get("language") in COMPILERS
    ]


def build_jobs(rows: list[dict[str, Any]], raw_root: Path) -> list[dict[str, Any]]:
    """Unique (compiler, sha256) compile jobs, deterministically ordered.

    Each job carries every source_record_id sharing those bytes, so one
    compile serves all duplicates (2375 rows -> ~2339 unique files).
    """
    jobs: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        lang = r.get("language")
        sha = r.get("source_code_sha256")
        if lang not in COMPILERS or not isinstance(sha, str) or not sha:
            continue  # cannot identify content -> row resolves to null later
        compiler = COMPILERS[lang]
        path = raw_root / str(r.get("source_code_path") or "")
        key = (compiler, sha)
        job = jobs.get(key)
        if job is None:
            jobs[key] = {
                "compiler": compiler,
                "sha256": sha,
                "path": path,
                "exists": path.is_file(),
                "record_ids": [r["source_record_id"]],
            }
        else:
            job["record_ids"].append(r["source_record_id"])
    return [jobs[k] for k in sorted(jobs)]


def wsl_path(path: Path) -> str:
    """Windows path -> WSL mount path (G:\\x -> /mnt/g/x)."""
    s = str(path).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/mnt/{s[0].lower()}{s[2:]}"
    return s


# -------------------------------------------------------------------- compile


_BASH_SCRIPT = """#!/bin/bash
set -u
manifest="$1"; outdir="$2"; workers="$3"
running=0
while IFS=$'\\t' read -r key comp src; do
  (
    if [ -f "$src" ]; then
      timeout 20 "$comp" {flags} -o /dev/null "$src" 2> "$outdir/$key.err"
      echo $? > "$outdir/$key.exit"
    else
      : > "$outdir/$key.err"
      echo 127 > "$outdir/$key.exit"
    fi
  ) &
  running=$((running + 1))
  if [ "$running" -ge "$workers" ]; then
    wait -n 2>/dev/null || wait
    running=$((running - 1))
  fi
done < "$manifest"
wait
"""


def wsl_compile(jobs: list[dict[str, Any]], work_dir: Path, workers: int) -> None:
    """Batch-compile pending jobs through WSL gcc/g++ (one boot, xargs-free
    bounded background loop so paths with spaces stay safe)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    manifest = work_dir / "manifest.tsv"
    # newline="\n": a CRLF here would make every `$src` end in \r and the bash
    # `[ -f ]` check would (wrongly) report the file missing — caught by the
    # first real run: every job exited 127.
    manifest.write_text(
        "".join(
            f'{job["compiler"]}-{job["sha256"]}\t{job["compiler"]}\t{wsl_path(job["path"])}\n'
            for job in jobs
        ),
        encoding="utf-8",
        newline="\n",
    )
    script = work_dir / "run.sh"
    script.write_text(
        _BASH_SCRIPT.format(flags=" ".join(COMPILE_FLAGS)),
        encoding="utf-8", newline="\n",
    )
    proc = subprocess.run(
        ["wsl", "-e", "bash", wsl_path(script), wsl_path(manifest),
         wsl_path(work_dir), str(workers)],
        capture_output=True, text=True, timeout=3600,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"WSL compile batch failed (exit {proc.returncode}): {proc.stderr[-2000:]}"
        )


def _job_key(job: dict[str, Any]) -> str:
    return f'{job["compiler"]}-{job["sha256"]}'


def _job_done(work_dir: Path, job: dict[str, Any]) -> bool:
    return (work_dir / f"{_job_key(job)}.exit").is_file()


def collect_results(work_dir: Path, jobs: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Read work-dir sidecars into {(compiler, sha): {compile_ok, flags}}.

    timeout (124) -> flags null: the stderr is incomplete and partial
    evidence must never masquerade as "-Wall ran clean" (§6).
    """
    results: dict[tuple[str, str], dict[str, Any]] = {}
    for job in jobs:
        key = _job_key(job)
        exit_file = work_dir / f"{key}.exit"
        if not exit_file.is_file():
            continue
        try:
            code = int(exit_file.read_text(encoding="utf-8").strip() or "-1")
        except (OSError, ValueError):
            code = -1
        if code == GNU_TIMEOUT_EXIT:
            results[(job["compiler"], job["sha256"])] = {"compile_ok": False, "flags": None}
            continue
        err_file = work_dir / f"{key}.err"
        try:
            stderr = err_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            stderr = None
        flags = parse_warnings(stderr)
        if isinstance(flags, list):
            flags = sorted(flags, key=lambda f: f["flag"])
        results[(job["compiler"], job["sha256"])] = {
            "compile_ok": code == 0,
            "flags": flags,
        }
    return results


def assemble_rows(
    rows: list[dict[str, Any]],
    results: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Fan out per-(compiler, sha) results to every source_record_id."""
    out: list[dict[str, Any]] = []
    for r in sorted(rows, key=lambda x: str(x.get("source_record_id"))):
        lang = r.get("language")
        sha = r.get("source_code_sha256")
        compiler = COMPILERS.get(lang) if isinstance(lang, str) else None
        res = results.get((compiler, sha)) if compiler and sha else None
        out.append({
            "source_record_id": r.get("source_record_id"),
            "language": lang,
            "compiler": compiler,
            "source_code_sha256": sha,
            "compile_ok": res["compile_ok"] if res else None,
            "flags": json.dumps(res["flags"]) if res and res["flags"] is not None else None,
        })
    return out


def run_extraction(
    rows: list[dict[str, Any]],
    raw_root: Path,
    work_dir: Path,
    *,
    runner: Runner | None = None,
    workers: int = 12,
) -> list[dict[str, Any]]:
    """Full pipeline: jobs -> compile pending (runner injectable) -> rows."""
    jobs = build_jobs(rows, raw_root)
    pending = [j for j in jobs if j["exists"] and not _job_done(work_dir, j)]
    if pending:
        work_dir.mkdir(parents=True, exist_ok=True)
        (runner or wsl_compile)(pending, work_dir, workers)
    results = collect_results(work_dir, jobs)
    return assemble_rows(rows, results)


def write_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_index(index_path: Path) -> list[dict[str, Any]]:
    with index_path.open(encoding="utf-8", errors="replace", newline="") as fh:
        return list(csv.DictReader(fh))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    ap.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--work-dir", type=Path, default=DEFAULT_WORK)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args(argv)

    index_rows = read_index(args.index)
    rows = select_rows(index_rows)
    print(f"index rows={len(index_rows)} selected PROGPEDIA c/cpp={len(rows)}")

    out_rows = run_extraction(rows, args.raw_root, args.work_dir, workers=args.workers)
    write_csv(out_rows, args.out)

    # report: coverage + the two pg signal flags
    from collections import Counter
    flag_counter: Counter[str] = Counter()
    ok = timeout_or_fail = nulls = 0
    for r in out_rows:
        if r["compile_ok"] is None:
            nulls += 1
        elif r["compile_ok"]:
            ok += 1
        else:
            timeout_or_fail += 1
        if r["flags"] is None:
            continue
        for f in json.loads(r["flags"]):
            flag_counter[f["flag"]] += f["count"]
    print(f"rows={len(out_rows)} compile_ok={ok} failed={timeout_or_fail} null={nulls}")
    print(f"-Wparentheses rows={sum(1 for r in out_rows if r['flags'] and '-Wparentheses' in r['flags'])}"
          f"  -Wmaybe-uninitialized rows={sum(1 for r in out_rows if r['flags'] and '-Wmaybe-uninitialized' in r['flags'])}")
    print("top flags:", ", ".join(f"{k}={v}" for k, v in flag_counter.most_common(8)))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
