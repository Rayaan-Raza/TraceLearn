"""Cluster-aware expansion of the synthetic mutant corpus.

The original generator anchors hand-written templates to a single problem, so
several misconception classes are confined to one or two problem clusters.
This script reuses the same operator library and verifier but selects
CodeStream seeds from the merge-authority *train* clusters, preferring clusters
where the class is under-represented.

It is intended to run under WSL (the host has no g++):

    python3 scripts/expand_mutants.py \
        --raw-root /mnt/g/TraceLearn/Datasets_RAW \
        --classes CPP_MISSING_BASE_CASE CPP_RANGE_CHECK \
        --clusters-per-class 3 --rows-per-cluster 5

Every accepted row is verified by execution, carries canonical tests/runtime
evidence, and is deduped on (seed_ref, mutation_op, problem_id, label).
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

# Support both `python -m scripts.expand_mutants` and
# `python scripts/expand_mutants.py` (the latter puts scripts/, not the repo
# root, on sys.path).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import generate_mutants as gm

csv.field_size_limit(10 ** 7)

ROOT = Path(gm.ROOT)
DEFAULT_DATASET_DIR = ROOT / "data" / "misconception_dataset"
DEFAULT_RAW_ROOT = Path("G:/TraceLearn/Datasets_RAW")
DEFAULT_CLASSES = (
    "CPP_MISSING_BASE_CASE",
    "CPP_RANGE_CHECK",
    "CPP_WRONG_LOOP_DIR",
    "CPP_INT_OVERFLOW",
    "CPP_STALE_EXIT",
    "CPP_UNINITIALIZED_VAR",
    "CPP_ASSIGN_VS_COMPARE",
    "CPP_LOOP_BOUNDARY",
    "CPP_OFF_BY_ONE",
)


# ------------------------------------------------------------------ selection


def deterministic_row_id(seed_id: str, operator: str, label: str, cluster: str) -> str:
    """Stable id so a rerun dedupes instead of duplicating rows."""
    digest = hashlib.sha256(
        f"{seed_id}|{operator}|{label}|{cluster}|expand-v1".encode("utf-8")
    ).hexdigest()[:10]
    return f"mut-{digest}"


def load_cluster_assignments(path: Path) -> dict[str, str]:
    """problem_id -> cluster_id for merge-authority TRAIN problems only."""
    out: dict[str, str] = {}
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if (row.get("split") or "").strip() == "train":
                out[row["problem_id"]] = row["cluster_id"]
    return out


def load_existing_keys(path: Path) -> set[tuple[str, str, str, str]]:
    """Existing (seed_ref, mutation_op, problem_id, label) triples."""
    keys: set[tuple[str, str, str, str]] = set()
    path = Path(path)
    if not path.is_file():
        return keys
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            seed_ref = row.get("seed_ref")
            op = row.get("mutation_op")
            pid = row.get("problem_id")
            label = row.get("label")
            if seed_ref and op and pid and label:
                keys.add((str(seed_ref), str(op), str(pid), str(label)))
    return keys


def select_target_clusters(
    class_cluster_counts: Counter[str],
    reachable_clusters: Iterable[str],
    max_clusters: int,
) -> list[str]:
    """Prefer clusters where the class has the fewest existing rows."""
    ordered = sorted(
        set(reachable_clusters),
        key=lambda c: (int(class_cluster_counts.get(c, 0)), str(c)),
    )
    return ordered[: max(0, int(max_clusters))]


def load_problem_context(path: Path) -> dict[str, dict[str, Any]]:
    """Canonical context block values from the raw Problem Data CSV."""
    out: dict[str, dict[str, Any]] = {}
    path = Path(path)
    if not path.is_file():
        return out
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            pid = gm.norm_pid(row.get("problem_id") or "")
            statement = (
                row.get("problem_statement")
                or row.get("problem_description")
                or row.get("statement")
                or row.get("description")
                or ""
            )
            tcs_raw = row.get("evaluation_test_cases") or "[]"
            try:
                tcs = json.loads(tcs_raw)
            except Exception:
                tcs = []
            context: dict[str, Any] = {
                "available": True,
                "statement_length": len(statement),
                "sample_test_count": len(tcs),
                "sample_tests_present": bool(tcs),
                "constraints_present": bool(
                    re.search(r"\bconstraints?\b", statement, re.IGNORECASE)
                ),
            }
            difficulty = row.get("difficulty")
            if difficulty not in (None, ""):
                try:
                    context["difficulty"] = float(difficulty)
                except ValueError:
                    pass
            out[pid] = context
    return out


# ------------------------------------------------------------------ evidence


def run_tests_rich(
    exe_path: str,
    tests: list[dict[str, Any]],
    run_cmd: Callable[..., tuple[int, str, str]] | None = None,
) -> dict[str, Any]:
    """Run tests and classify each result as pass/wrong/crash/timeout."""
    runner = run_cmd or gm.run_cmd
    results: list[dict[str, Any]] = []
    passed = failed = 0
    for tc in tests:
        inp = tc.get("input", "")
        expected = (tc.get("output") or tc.get("expected", "")).strip()
        rc, stdout, stderr = runner(
            [exe_path], gm.RUN_TIMEOUT, stdin_text=inp
        )
        timed_out = rc == -1 and stderr.strip() == "TIMEOUT"
        actual = stdout.strip()
        if rc == 0 and actual == expected:
            status = "pass"
            passed += 1
        elif timed_out:
            status = "timeout"
            failed += 1
        elif rc == 0:
            status = "wrong"
            failed += 1
        else:
            status = "crash"
            failed += 1
        results.append({
            "test_no": tc.get("test_case_no", "?"),
            "status": status,
            "passed": status == "pass",
            "rc": rc,
            "stdout": stdout[:500],
            "stderr": stderr[:500],
            "timed_out": timed_out,
        })
    return {
        "total": len(tests),
        "passed": passed,
        "failed": failed,
        "results": results,
    }


def build_tests_block(results: dict[str, Any]) -> dict[str, Any]:
    """Map rich test results onto the canonical tests block."""
    details = results.get("results") or []
    total = int(results.get("total") or len(details))
    passed = int(results.get("passed") or 0)
    failed = int(results.get("failed") or max(0, total - passed))
    wrong = sum(1 for r in details if r.get("status") == "wrong")
    runtime_errors = sum(1 for r in details if r.get("status") == "crash")
    timeouts = sum(1 for r in details if r.get("status") == "timeout")
    first_fail = -1
    for index, result in enumerate(details):
        if result.get("status") != "pass":
            first_fail = index
            break
    block: dict[str, Any] = {
        "available": True,
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": (passed / total) if total else 0.0,
        "wrong_answer_count": wrong,
        "runtime_error_count": runtime_errors,
        "timeout_count": timeouts,
    }
    if first_fail >= 0:
        block["first_fail_index"] = first_fail
    # boundary_fail_count / first_fail_numeric_diff need per-test metadata the
    # raw test cases do not carry -> leave NaN (never fabricate a zero).
    return block


def build_runtime_block(
    results: dict[str, Any],
    sanitizer_stderr: str = "",
    sanitizer_ran: bool = False,
) -> dict[str, Any]:
    """Map execution + sanitizer evidence onto the canonical runtime block."""
    details = results.get("results") or []
    crashed = any(r.get("status") == "crash" for r in details)
    timed_out = any(r.get("status") == "timeout" for r in details)
    block: dict[str, Any] = {
        "available": True,
        "crashed": crashed,
        "timed_out": timed_out,
    }
    first_rc = next(
        (int(r.get("rc")) for r in details if isinstance(r.get("rc"), int)),
        None,
    )
    if first_rc is not None:
        if first_rc >= 0:
            block["exit_code"] = first_rc
        elif first_rc < -1:
            block["signal"] = abs(first_rc)
    if sanitizer_ran:
        low = sanitizer_stderr.lower()
        block["asan_error"] = "addresssanitizer" in low
        block["asan_heap_buffer_overflow"] = "heap-buffer-overflow" in low
        block["asan_stack_buffer_overflow"] = "stack-buffer-overflow" in low
        block["ubsan_error"] = (
            "runtime error:" in low or "undefinedbehaviorsanitizer" in low
        )
        block["ubsan_signed_overflow"] = "signed integer overflow" in low
        block["stack_overflow"] = (
            "stack overflow" in low or "stack-overflow" in low
        )
    return block


def build_expansion_row(
    seed: dict[str, Any],
    mutant_code: str,
    label: str,
    operator: str,
    proof: dict[str, Any],
    cluster: str,
    pipeline_run_id: str,
) -> dict[str, Any]:
    """Build a tier0 row with canonical evidence blocks filled in."""
    row_id = deterministic_row_id(
        str(seed["submission_id"]), operator, label, cluster
    )
    row = gm.make_row(
        row_id, seed, mutant_code, label, operator, proof, cluster,
        pipeline_run_id,
    )
    row["schema_version"] = "1.1"
    row["problem_cluster"] = cluster
    row["runtime"] = copy.deepcopy(proof.get("runtime") or {})
    row["tests"] = copy.deepcopy(proof.get("tests") or {})
    row["context"] = copy.deepcopy(proof.get("context") or {})
    return row


# ------------------------------------------------------------------ verifier


class RichVerifier:
    """Compile/run verifier that records canonical tests/runtime evidence."""

    def __init__(
        self,
        work_dir: Path,
        proofs_dir: Path,
        problem_tests: dict[str, list[dict[str, Any]]],
        contexts: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.work_dir = Path(work_dir)
        self.proofs_dir = Path(proofs_dir)
        self.problem_tests = problem_tests
        self.contexts = contexts or {}
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.proofs_dir.mkdir(parents=True, exist_ok=True)

    def _tests_for(self, seed: dict[str, Any]) -> list[dict[str, Any]]:
        inline = seed.get("_inline_tests")
        if inline:
            return inline
        return self.problem_tests.get(seed["problem_id"], [])

    def verify_seed(self, seed: dict[str, Any]) -> tuple[bool, str]:
        tests = self._tests_for(seed)
        if not tests:
            return False, "no_tests"
        sid = str(seed["submission_id"]).replace("/", "_")
        exe = self.work_dir / f"seed_{sid}.exe"
        ok, stderr = gm.compile_cpp(seed["source_code"], str(exe))
        if not ok:
            return False, f"compile_fail: {stderr[:160]}"
        results = run_tests_rich(str(exe), tests)
        try:
            exe.unlink(missing_ok=True)
        except Exception:
            pass
        if results["failed"] > 0:
            return False, f"seed_fails_{results['failed']}_tests"
        return True, "ok"

    def verify_mutant(
        self,
        seed: dict[str, Any],
        mutant_code: str,
        label: str,
        operator: str,
        cluster: str,
    ) -> tuple[bool, dict[str, Any]]:
        tests = self._tests_for(seed)
        if not tests:
            return False, {"reason": "no_tests"}

        row_id = deterministic_row_id(
            str(seed["submission_id"]), operator, label, cluster
        )
        run_id = row_id[4:]
        exe_std = self.work_dir / f"mut_{run_id}.exe"
        ok_std, stderr_std = gm.compile_cpp(
            mutant_code, str(exe_std), "standard"
        )
        if not ok_std:
            return False, {
                "reason": "mutant_compile_fail",
                "stderr": stderr_std[:400],
            }

        results = run_tests_rich(str(exe_std), tests)
        sanitizer_ran = False
        sanitizer_stderr = ""
        exe_san = self.work_dir / f"mut_{run_id}_san.exe"
        if results["failed"] == 0:
            try:
                free = shutil.disk_usage(self.work_dir).free
                if free > 200 * 1024 * 1024:
                    ok_san, stderr_san = gm.compile_cpp(
                        mutant_code, str(exe_san), "sanitizer"
                    )
                    if ok_san:
                        sanitizer_ran = True
                        san_results = run_tests_rich(str(exe_san), tests)
                        sanitizer_stderr = "\n".join(
                            r.get("stderr", "")
                            for r in san_results.get("results", [])
                            if r.get("stderr")
                        )
                        if san_results["failed"] > 0:
                            results = san_results
                    else:
                        sanitizer_stderr = stderr_san
            except Exception:
                pass

        if results["failed"] == 0:
            return False, {"reason": "mutant_passes_all_tests"}

        collisions = gm.check_collision(
            seed["source_code"], mutant_code, label
        )
        if collisions:
            return False, {"reason": f"collision_with_{'+'.join(collisions)}"}

        proof: dict[str, Any] = {
            "run_id": run_id,
            "seed_submission_id": seed["submission_id"],
            "problem_id": seed["problem_id"],
            "operator": operator,
            "label": label,
            "seed_sha256": gm.sha256(seed["source_code"]),
            "mutant_sha256": gm.sha256(mutant_code),
            "compile_warnings_std": stderr_std[:500] if stderr_std else "",
            "sanitizer_ok": sanitizer_ran,
            "tests_passed": results["passed"],
            "tests_failed": results["failed"],
            "tests_total": results["total"],
            "tests": build_tests_block(results),
            "runtime": build_runtime_block(
                results, sanitizer_stderr, sanitizer_ran
            ),
            "context": {} if seed.get("_template") else copy.deepcopy(
                self.contexts.get(seed["problem_id"]) or {}
            ),
            "test_details": results["results"][:10],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        proof_path = self.proofs_dir / f"{run_id}.json"
        proof_path.write_text(
            json.dumps(proof, indent=2), encoding="utf-8"
        )

        for exe in (exe_std, exe_san):
            try:
                exe.unlink(missing_ok=True)
            except Exception:
                pass
        return True, proof


# ------------------------------------------------------------------ raw paths


def resolve_raw_csvs(raw_root: Path) -> tuple[Path, Path]:
    """Locate Submission Data.csv and Problem Data.csv under the raw root."""
    root = Path(raw_root)
    submissions = sorted(root.rglob("Submission Data.csv"))
    problems = sorted(root.rglob("Problem Data.csv"))
    if not submissions or not problems:
        raise FileNotFoundError(
            f"could not find Submission/Problem Data.csv under {root}"
        )
    return submissions[0], problems[0]


def _backup_once(path: Path) -> None:
    backup = path.with_name(path.name + ".pre_expansion")
    if path.is_file() and not backup.exists():
        shutil.copy2(path, backup)


# ------------------------------------------------------------------ main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--proofs-dir", type=Path, default=None)
    parser.add_argument("--classes", nargs="*", default=list(DEFAULT_CLASSES))
    parser.add_argument("--clusters-per-class", type=int, default=3)
    parser.add_argument("--rows-per-cluster", type=int, default=5)
    parser.add_argument("--max-attempts", type=int, default=30)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args(argv)

    if args.pilot:
        args.clusters_per_class = min(args.clusters_per_class, 2)
        args.rows_per_cluster = min(args.rows_per_cluster, 2)
        args.max_attempts = min(args.max_attempts, 10)

    dataset_dir = Path(args.dataset_dir)
    out_path = Path(args.out) if args.out else (
        dataset_dir / "annotations" / "tier0_mutants.jsonl"
    )
    proofs_dir = Path(args.proofs_dir) if args.proofs_dir else (
        dataset_dir / "annotations" / "mutant_proofs"
    )
    reports_dir = dataset_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    submissions_csv, problems_csv = resolve_raw_csvs(Path(args.raw_root))
    gm.CODESTREAM_CSV = str(submissions_csv)
    gm.PROBLEMS_CSV = str(problems_csv)

    clusters = load_cluster_assignments(
        dataset_dir / "splits" / "cluster_assignments.csv"
    )
    train_problems = set(clusters)
    problem_tests = gm.load_problem_tests()
    seeds = gm.load_seeds(train_problems)
    contexts = load_problem_context(problems_csv)
    lib = gm.load_operator_library()

    print(
        f"raw: {submissions_csv} | train problems={len(train_problems)} | "
        f"seeds={len(seeds)} | problems with tests={len(problem_tests)}"
    )
    if not seeds:
        print("ERROR: no CodeStream seeds for merge-authority train problems")
        return 1

    existing_keys = load_existing_keys(out_path)
    existing_ids: set[str] = set()
    class_cluster_counts: Counter[str] = Counter()
    if out_path.is_file():
        with out_path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                existing_ids.add(str(row.get("row_id")))
                if row.get("label") in args.classes:
                    # The merge assigns the split/cluster from
                    # cluster_assignments.csv, not from the row's own
                    # problem_cluster field. Count under the authority so
                    # target selection sees real cluster coverage.
                    cluster = clusters.get(str(row.get("problem_id"))) or row.get(
                        "problem_cluster"
                    )
                    if cluster:
                        class_cluster_counts[
                            f"{row['label']}|{cluster}"
                        ] += 1

    # The key used for selection is per-class; keep a helper view.
    per_class_counts: dict[str, Counter[str]] = {
        cls: Counter() for cls in args.classes
    }
    for composite, count in class_cluster_counts.items():
        label, _, cluster = composite.partition("|")
        if label in per_class_counts:
            per_class_counts[label][cluster] += count

    verifier = RichVerifier(
        work_dir=dataset_dir / "annotations" / "_expand_work",
        proofs_dir=proofs_dir,
        problem_tests=problem_tests,
        contexts=contexts,
    )
    seed_ok: dict[str, tuple[bool, str]] = {}
    pipeline_run_id = "run-expand-v1"
    new_rows: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "raw_submissions": str(submissions_csv),
        "raw_problems": str(problems_csv),
        "classes": {},
        "reject_reasons": {},
        "dry_run": bool(args.dry_run),
        "pilot": bool(args.pilot),
    }

    for cls in args.classes:
        forms = (lib.get("operators", {}).get(cls) or {}).get("forms") or []
        if not forms:
            print(f"{cls}: no operator forms, skipped")
            continue

        pairs_by_cluster: dict[str, list[tuple[dict, dict, str]]] = defaultdict(list)
        for seed in seeds:
            cluster = clusters.get(seed["problem_id"])
            if not cluster:
                continue
            for form in forms:
                mutant = gm.apply_operator_form(seed["source_code"], form)
                if mutant:
                    pairs_by_cluster[cluster].append((seed, form, mutant))

        # Hand-written templates are the fallback when CodeStream seeds lack
        # a syntactically safe form (MBC's remove-return form leaves a
        # dangling `else`). Re-anchor each template to one train problem per
        # target cluster so the merge can spread it across clusters. The
        # verifier still compiles/runs the template's own inline tests.
        templates = gm.SEED_TEMPLATES.get(cls, [])
        if templates:
            cluster_to_problem: dict[str, str] = {}
            for pid, cluster in sorted(clusters.items()):
                cluster_to_problem.setdefault(cluster, pid)
            for cluster, pid in cluster_to_problem.items():
                for index, template in enumerate(templates):
                    seed = dict(template)
                    seed["problem_id"] = pid
                    seed["language"] = "cpp"
                    seed["attempt_number"] = None
                    seed["user_id"] = f"template_{cls}"
                    seed["_template"] = True
                    seed.setdefault(
                        "submission_id", f"tpl-{cls}-{index:03d}"
                    )
                    for form in forms:
                        mutant = gm.apply_operator_form(
                            seed["source_code"], form
                        )
                        if mutant:
                            pairs_by_cluster[cluster].append(
                                (seed, form, mutant)
                            )

        targets = select_target_clusters(
            per_class_counts[cls], pairs_by_cluster.keys(),
            args.clusters_per_class,
        )
        class_report: dict[str, Any] = {
            "target_clusters": targets,
            "reachable_clusters": sorted(pairs_by_cluster),
            "accepted": {},
            "reject_reasons": {},
        }
        class_new = 0
        for cluster in targets:
            accepted = 0
            attempts = 0
            rejects: Counter[str] = Counter()
            pairs = sorted(
                pairs_by_cluster[cluster],
                key=lambda p: (str(p[0]["submission_id"]), str(p[1]["name"])),
            )
            for seed, form, mutant in pairs:
                if accepted >= args.rows_per_cluster:
                    break
                if attempts >= args.max_attempts:
                    break
                op = str(form["name"])
                key = (
                    str(seed["submission_id"]), op,
                    str(seed["problem_id"]), cls,
                )
                if key in existing_keys:
                    continue
                row_id = deterministic_row_id(
                    str(seed["submission_id"]), op, cls, cluster
                )
                if row_id in existing_ids:
                    continue
                attempts += 1

                if args.dry_run:
                    # Reachability only: no compiler / seed execution.
                    accepted += 1
                    class_new += 1
                    existing_keys.add(key)
                    existing_ids.add(row_id)
                    continue

                sid = str(seed["submission_id"])
                if sid not in seed_ok:
                    seed_ok[sid] = verifier.verify_seed(seed)
                ok_seed, seed_reason = seed_ok[sid]
                if not ok_seed:
                    rejects[f"seed:{seed_reason}"] += 1
                    continue

                ok, proof = verifier.verify_mutant(
                    seed, mutant, cls, op, cluster
                )
                if not ok:
                    rejects[str(proof.get("reason", "rejected"))] += 1
                    continue

                row = build_expansion_row(
                    seed, mutant, cls, op, proof, cluster, pipeline_run_id
                )
                new_rows.append(row)
                existing_keys.add(key)
                existing_ids.add(row_id)
                per_class_counts[cls][cluster] += 1
                accepted += 1
                class_new += 1

            class_report["accepted"][cluster] = accepted
            class_report["reject_reasons"][cluster] = dict(rejects)
            print(
                f"{cls} / {cluster}: accepted={accepted} "
                f"attempts={attempts} rejects={dict(rejects)}"
            )
        class_report["new_rows"] = class_new
        report["classes"][cls] = class_report

    if not args.dry_run and new_rows:
        _backup_once(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("a", encoding="utf-8", newline="\n") as fh:
            for row in new_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    report["n_new"] = len(new_rows)
    report["out"] = str(out_path)
    (reports_dir / "expansion_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8", newline="\n"
    )
    print(
        f"done: new_rows={len(new_rows)} "
        f"{'(dry-run)' if args.dry_run else ''} -> {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
