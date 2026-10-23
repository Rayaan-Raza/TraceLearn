#!/usr/bin/env python3
"""Verify raw data recovery (master plan §9.0 G0).

Checks, in order:
1. CodeNet problem-dir count (70 by default).
2. PROGpedia copy dir counts (9 + 8 by default).
3. CodeStream CSV row counts (46 problems, 5,482 submissions by default).
4. 100% of *labeled-pool* paths resolve — CODESTREAM + PROGPEDIA rows in the
   normalized submissions index only. CodeNet is excluded from labels, so a
   broken CodeNet path never fails G0 (§2.1).
5. A deterministic SHA-256 sample of the labeled pool at >=98% match,
   recomputing each source's hash the same way `ingest_sources.py` did
   (file bytes for PROGPEDIA; .strip()'d source_code for CodeStream).

Writes raw_recovery/recovery_manifest.json (always, even on failure), prints
one PASS/FAIL line per check, and exits 0 only when every check passes.
Docker digest (G0b, Umaima) and seed audit (G0c, Eman) are explicit nulls —
this script never invents another lane's evidence.

Rules:
1. Read only. Change nothing except the manifest it writes.
2. Exit 1 when any check fails.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_ROOT = Path(r"G:\TraceLearn\Datasets_RAW")
DEFAULT_NORMALIZED = (
    ROOT / "data" / "Data_from_Datasets" / "intermediate" / "normalized"
)
DEFAULT_OUT = ROOT / "data" / "misconception_dataset" / "raw_recovery" / "recovery_manifest.json"

LABELED_SOURCES = {"CODESTREAM", "PROGPEDIA"}
CS_DIR = "CodeStream A Dataset of Iterative Programming Subm"
CODE_EXTENSIONS = {".c": "c", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp"}

failures: list[str] = []


@dataclass(frozen=True)
class RecoveryExpectations:
    """G0 gate numbers. Defaults are the master plan's exact figures."""

    codenet_problem_dirs: int = 70
    progpedia_copies: tuple[int, int] = (9, 8)
    codestream_problems: int = 46
    codestream_submissions: int = 5482
    sha_sample_frac: float = 0.05
    sha_min_rate: float = 0.98


def check(label: str, ok: bool, detail: str = "") -> None:
    """Print one check result and record a failure when it does not pass."""
    mark = "PASS" if ok else "FAIL"
    print(f"{label:<38} {mark}  {detail}")
    if not ok:
        failures.append(label)


def _read_text(path: Path) -> str:
    """Decode a raw file the way ingest_sources.py did."""
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _count_dirs(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for p in path.iterdir() if p.is_dir())


def _count_csv_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    reader = csv.reader(io.StringIO(_read_text(path), newline=""))
    next(reader, None)  # header
    return sum(1 for _ in reader)


def _load_labeled_pool(submissions_csv: Path) -> list[dict[str, str]]:
    """Stream the labeled pool (CODESTREAM + PROGPEDIA rows) from the index."""
    pool: list[dict[str, str]] = []
    if not submissions_csv.is_file():
        return pool
    with submissions_csv.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if (row.get("dataset_source") or "") in LABELED_SOURCES:
                pool.append(
                    {
                        "submission_id": row.get("submission_id") or "",
                        "dataset_source": row.get("dataset_source") or "",
                        "source_code_path": row.get("source_code_path") or "",
                        "source_code_sha256": row.get("source_code_sha256") or "",
                    }
                )
    return pool


class _CodeStreamIndex:
    """Lazy sid -> source_code lookup over referenced CodeStream CSVs."""

    def __init__(self, raw_root: Path) -> None:
        self.raw_root = raw_root
        self._cache: dict[str, dict[str, str] | None] = {}

    def _rows(self, rel_csv: str) -> dict[str, str] | None:
        if rel_csv not in self._cache:
            path = self.raw_root / rel_csv
            if not path.is_file():
                self._cache[rel_csv] = None
            else:
                text = _read_text(path)
                reader = csv.DictReader(io.StringIO(text, newline=""))
                self._cache[rel_csv] = {
                    (r.get("submission_id") or "").strip(): (
                        (r.get("source_code") or "").strip()
                    )
                    for r in reader
                }
        return self._cache[rel_csv]

    def resolve(self, anchor: str) -> tuple[bool, str, str]:
        """Return (found, reason, code). anchor is `<csv>#<sid>`."""
        if "#" not in anchor:
            return False, "malformed_anchor", ""
        rel_csv, _, sid = anchor.partition("#")
        rows = self._rows(rel_csv)
        if rows is None:
            return False, "csv_missing", ""
        if sid not in rows:
            return False, "submission_id_not_in_csv", ""
        return True, "", rows[sid]


def resolve_paths(
    pool: list[dict[str, str]], raw_root: Path
) -> dict:
    """Resolve 100% of labeled-pool source_code_path anchors."""
    cs_index = _CodeStreamIndex(raw_root)
    resolved = 0
    unresolved: list[dict[str, str]] = []
    for row in pool:
        ref = row["source_code_path"]
        ok, reason = False, ""
        if row["dataset_source"] == "PROGPEDIA":
            if not ref:
                reason = "empty_path"
            elif (raw_root / ref).is_file():
                ok = True
            else:
                reason = "file_missing"
        else:  # CODESTREAM
            if not ref:
                reason = "empty_path"
            else:
                ok, reason, _ = cs_index.resolve(ref)
        if ok:
            resolved += 1
        else:
            unresolved.append(
                {
                    "submission_id": row["submission_id"],
                    "source_code_path": ref,
                    "reason": reason,
                }
            )
    return {
        "labeled_pool_rows": len(pool),
        "resolved": resolved,
        "pass": resolved == len(pool),
        "failures": unresolved[:20],
        "failures_total": len(unresolved),
    }


def sha256_sample(
    pool: list[dict[str, str]],
    raw_root: Path,
    frac: float,
    min_rate: float,
    seed: int,
) -> dict:
    """Deterministic SHA-256 sample; recomputes hashes as ingest_sources.py did."""
    ordered = sorted(pool, key=lambda r: r["submission_id"])
    n = len(ordered)
    k = min(n, max(1 if (frac > 0 and n) else 0, int(round(n * frac))))
    rng = random.Random(seed)
    picked = sorted(rng.sample(ordered, k), key=lambda r: r["submission_id"]) if k else []
    cs_index = _CodeStreamIndex(raw_root)

    matched = 0
    mismatches: list[dict[str, str]] = []
    for row in picked:
        expected = row["source_code_sha256"]
        actual = ""
        if row["dataset_source"] == "PROGPEDIA":
            path = raw_root / row["source_code_path"]
            if path.is_file():
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            found, _, code = cs_index.resolve(row["source_code_path"])
            if found:
                actual = hashlib.sha256(code.encode("utf-8")).hexdigest()
        if actual and actual == expected:
            matched += 1
        else:
            mismatches.append(
                {
                    "submission_id": row["submission_id"],
                    "source_code_path": row["source_code_path"],
                    "expected": expected,
                    "actual": actual or "<unresolvable>",
                }
            )
    rate = (matched / k) if k else 1.0
    return {
        "frac": frac,
        "seed": seed,
        "sampled": k,
        "matched": matched,
        "rate": rate,
        "threshold": min_rate,
        "pass": rate >= min_rate,
        "sampled_ids": [r["submission_id"] for r in picked],
        "mismatches": mismatches[:20],
    }


def verify(
    raw_root: Path,
    normalized_dir: Path,
    expectations: RecoveryExpectations,
    out_path: Path | None = None,
    seed: int = 0,
) -> tuple[dict, bool]:
    """Run every G0 check. Returns (manifest, all_passed). Always writes."""
    global failures
    failures = []

    checks: dict[str, dict] = {}

    def add(name: str, expected: int, observed: int) -> None:
        ok = observed == expected
        checks[name] = {"expected": expected, "observed": observed, "pass": ok}
        check(name, ok, f"expected {expected}, observed {observed}")

    add(
        "codenet_problem_dirs",
        expectations.codenet_problem_dirs,
        _count_dirs(raw_root / "Project_CodeNet" / "Project_CodeNet" / "data"),
    )
    add(
        "progpedia_copy_1_dirs",
        expectations.progpedia_copies[0],
        _count_dirs(raw_root / "progpedia"),
    )
    add(
        "progpedia_copy_2_dirs",
        expectations.progpedia_copies[1],
        _count_dirs(raw_root / "progpedia (1)"),
    )
    add(
        "codestream_problem_rows",
        expectations.codestream_problems,
        _count_csv_rows(raw_root / CS_DIR / "Problem Data.csv"),
    )
    add(
        "codestream_submission_rows",
        expectations.codestream_submissions,
        _count_csv_rows(raw_root / CS_DIR / "Submission Data.csv"),
    )

    pool = _load_labeled_pool(normalized_dir / "submissions" / "submissions.csv")
    resolution = resolve_paths(pool, raw_root)
    check(
        "labeled_pool_paths_resolve",
        resolution["pass"],
        f"{resolution['resolved']}/{resolution['labeled_pool_rows']}",
    )

    sample = sha256_sample(
        pool,
        raw_root,
        expectations.sha_sample_frac,
        expectations.sha_min_rate,
        seed,
    )
    check(
        "sha256_sample",
        sample["pass"],
        f"{sample['matched']}/{sample['sampled']} = {sample['rate']:.4f} "
        f"(>= {sample['threshold']})",
    )

    ingest_manifest = normalized_dir / "ingest_run_manifest.json"
    ingest_flags = None
    if ingest_manifest.is_file():
        try:
            ingest_flags = json.loads(
                ingest_manifest.read_text(encoding="utf-8")
            ).get("flags")
        except (json.JSONDecodeError, OSError):
            ingest_flags = None

    manifest = {
        "kind": "raw_recovery",
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "raw_root": str(raw_root),
        "normalized_dir": str(normalized_dir),
        "checks": checks,
        "path_resolution": resolution,
        "sha256_sample": sample,
        "ingest_flags": ingest_flags,
        # Owned by other lanes; explicit nulls until they ship evidence.
        "g0b_docker_digest": None,
        "g0c_seed_audit": None,
    }

    ok = not failures
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest, ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--normalized", type=Path, default=DEFAULT_NORMALIZED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--codenet-dirs", type=int, default=70)
    parser.add_argument("--progpedia-copies", type=int, nargs=2, default=[9, 8])
    parser.add_argument("--codestream-problems", type=int, default=46)
    parser.add_argument("--codestream-submissions", type=int, default=5482)
    parser.add_argument("--sample-frac", type=float, default=0.05)
    parser.add_argument("--sha-min-rate", type=float, default=0.98)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    expectations = RecoveryExpectations(
        codenet_problem_dirs=args.codenet_dirs,
        progpedia_copies=tuple(args.progpedia_copies),
        codestream_problems=args.codestream_problems,
        codestream_submissions=args.codestream_submissions,
        sha_sample_frac=args.sample_frac,
        sha_min_rate=args.sha_min_rate,
    )
    _, ok = verify(
        args.raw_root, args.normalized, expectations, out_path=args.out, seed=args.seed
    )
    print(f"manifest: {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
