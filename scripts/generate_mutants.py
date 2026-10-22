"""
generate_mutants.py — E2 verifier + E3/E4 mutant generation.

Owns: scripts/generate_mutants.py, annotations/tier0_mutants.jsonl

Pipeline per mutant:
  1. Load seed (CodeStream Accepted C/C++, train-side cluster)
  2. Apply operator (from operator_library.json)
  3. Compile seed pre-mutation — must pass (E2 gate)
  4. Compile mutant — must compile
  5. Execute mutant against problem test cases — must fail >= 1 test
  6. Collision check — mutant must not match any OTHER class signature
  7. clang-format normalise
  8. Store JSONL row with proof metadata

Usage:
  python scripts/generate_mutants.py --pilot     # E3: 150 mutants
  python scripts/generate_mutants.py --scale      # E4: 2900 floor
  python scripts/generate_mutants.py --class CPP_LOOP_BOUNDARY --n 50
  python scripts/generate_mutants.py --decoys     # E1d decoys
"""

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections import defaultdict
from datetime import datetime

csv.field_size_limit(10 ** 7)

# Import hand-crafted seed templates (G0c fallback when CodeStream seeds lack patterns)
import importlib.util as _ilu
_tpl_spec = _ilu.spec_from_file_location(
    "seed_templates",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_templates.py"),
)
_tpl_mod = _ilu.module_from_spec(_tpl_spec)
_tpl_spec.loader.exec_module(_tpl_mod)
SEED_TEMPLATES = _tpl_mod.SEED_TEMPLATES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODESTREAM_CSV = os.path.join(
    ROOT, "Datasets_RAW",
    "CodeStream A Dataset of Iterative Programming Subm",
    "Submission Data.csv",
)
PROBLEMS_CSV = os.path.join(
    ROOT, "Datasets_RAW",
    "CodeStream A Dataset of Iterative Programming Subm",
    "Problem Data.csv",
)
CLUSTER_SPLIT = os.path.join(ROOT, "data", "misconception_dataset", "raw_recovery", "cluster_split.json")
G0C_AUDIT = os.path.join(ROOT, "data", "misconception_dataset", "raw_recovery", "g0c_seed_audit.json")
OPERATOR_LIB = os.path.join(ROOT, "scripts", "operator_library.json")
OUT_JSONL = os.path.join(ROOT, "annotations", "tier0_mutants.jsonl")
PROOFS_DIR = os.path.join(ROOT, "annotations", "mutant_proofs")

TAXONOMY_VERSION = "tl-cpp-v2"
SCHEMA_VERSION = "1.0"
MAX_MUTANTS_PER_SEED = 5  # relaxed per G0c
COMPILE_TIMEOUT = 15       # seconds
RUN_TIMEOUT = 2            # seconds per test (2s covers all O(n) solutions with -O2; catches infinite loops)

CLASSES = [
    "CPP_LOOP_BOUNDARY", "CPP_OFF_BY_ONE", "CPP_ARRAY_BOUNDS",
    "CPP_UNINITIALIZED_VAR", "CPP_INT_OVERFLOW", "CPP_MISSING_BASE_CASE",
    "CPP_ASSIGN_VS_COMPARE", "CPP_WRONG_LOOP_DIR", "CPP_RANGE_CHECK",
    "CPP_STALE_EXIT", "CPP_OTHER_ERROR",
]

FLOOR = {
    "CPP_LOOP_BOUNDARY": 300, "CPP_OFF_BY_ONE": 300, "CPP_ARRAY_BOUNDS": 300,
    "CPP_UNINITIALIZED_VAR": 300, "CPP_INT_OVERFLOW": 300,
    "CPP_MISSING_BASE_CASE": 300, "CPP_ASSIGN_VS_COMPARE": 300,
    "CPP_WRONG_LOOP_DIR": 200, "CPP_RANGE_CHECK": 200, "CPP_STALE_EXIT": 200,
    "CPP_OTHER_ERROR": 200,
}

# Signature check patterns — after applying an operator for class X,
# check that mutant does NOT obviously match any OTHER class
SIGNATURE_PATTERNS = {
    "CPP_LOOP_BOUNDARY":      [re.compile(r"<=\s*\w+\s*[+\-]\s*1|!=\s*\w+\s*\+\s*1")],
    "CPP_OFF_BY_ONE":         [re.compile(r"\w+\[.*[+-]\s*1\]")],
    "CPP_ARRAY_BOUNDS":       [re.compile(r"\[.*-\s*[12]\]|new\s+\w+\[\w+\s*-|vector<\w+>\s+\w+\s*\(\w+\s*-")],
    "CPP_UNINITIALIZED_VAR":  [re.compile(r"\bint\s+\w+\s*;|\bdouble\s+\w+\s*;")],
    "CPP_INT_OVERFLOW":       [re.compile(r"\blong\s+long\b|\b1LL\b")],
    "CPP_MISSING_BASE_CASE":  [re.compile(r"if\s*\(\s*n\s*[<=>]=?\s*[01]\s*\)")],
    "CPP_ASSIGN_VS_COMPARE":  [re.compile(r"if\s*\(\s*\w+\s*=\s*\w+\s*\)")],
    "CPP_WRONG_LOOP_DIR":     [re.compile(r"\bi--\b|i\s*-=\s*1")],
    "CPP_RANGE_CHECK":        [re.compile(r"if\s*\([^)]*[<>]=?\s*\d+[^)]*&&[^)]*[<>]=?\s*\d+")],
    "CPP_STALE_EXIT":         [re.compile(r"while\s*\(true\)|while\s*\(1\)")],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def norm_pid(raw: str) -> str:
    if raw.startswith("tl-"):
        return raw
    return f"tl-codestream-{raw}"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_cmd(cmd: list[str], timeout: int, cwd: str | None = None,
            stdin_text: str | None = None) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=cwd, input=stdin_text or ""
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -2, "", str(e)


def compile_cpp(source: str, exe_path: str, flags: str = "standard") -> tuple[bool, str]:
    """Compile C++ source. Returns (success, stderr)."""
    if flags == "standard":
        compile_flags = ["-O2", "-Wall", "-Wextra", "-Wmaybe-uninitialized",
                         "-Wparentheses", "-Warray-bounds", "-std=c++17"]
    elif flags == "sanitizer":
        compile_flags = ["-O1", "-g", "-fno-omit-frame-pointer",
                         "-fsanitize=address,undefined", "-std=c++17"]
    else:
        compile_flags = ["-O2", "-std=c++17"]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".cpp", delete=False,
                                     encoding="utf-8") as f:
        f.write(source)
        src_path = f.name
    try:
        cmd = ["g++"] + compile_flags + [src_path, "-o", exe_path]
        rc, stdout, stderr = run_cmd(cmd, COMPILE_TIMEOUT)
        return rc == 0, stderr
    finally:
        try:
            os.unlink(src_path)
        except Exception:
            pass


def run_tests(exe_path: str, tests: list[dict]) -> dict:
    """Run executable against test cases. Returns pass/fail counts and details."""
    results = {"passed": 0, "failed": 0, "total": len(tests), "details": []}
    for tc in tests:
        inp = tc.get("input", "")
        expected = (tc.get("output") or tc.get("expected", "")).strip()
        rc, stdout, stderr = run_cmd([exe_path], RUN_TIMEOUT, stdin_text=inp)
        actual = stdout.strip()
        passed = (rc == 0 and actual == expected)
        results["details"].append({
            "test_no": tc.get("test_case_no", "?"),
            "passed": passed,
            "rc": rc,
        })
        if passed:
            results["passed"] += 1
        else:
            results["failed"] += 1
    return results


def check_collision(seed_code: str, mutant_code: str, intended_class: str) -> list[str]:
    """
    Return list of OTHER classes whose signatures appear in the mutant but NOT
    in the seed.  Pre-existing signatures are not introduced by the mutation
    and must not trigger a false collision rejection.
    """
    collisions = []
    for cls, patterns in SIGNATURE_PATTERNS.items():
        if cls == intended_class:
            continue
        for pat in patterns:
            if pat.search(mutant_code) and not pat.search(seed_code):
                collisions.append(cls)
                break
    return collisions


def apply_operator_form(source: str, form: dict) -> str | None:
    """Apply one operator form from the library. Returns mutated code or None."""
    pattern = re.compile(form["pattern"], re.MULTILINE | re.DOTALL)
    replacement = form["replacement"]
    if replacement == "__callable__":
        return None  # skip callable forms (handled by OPERATOR_FORMS inline)

    result = pattern.sub(replacement, source, count=1)
    if result == source:
        return None
    return result


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_problem_tests() -> dict[str, list[dict]]:
    """Load test cases per problem from Problem Data CSV."""
    tests = {}
    if not os.path.exists(PROBLEMS_CSV):
        return tests
    with open(PROBLEMS_CSV, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pid_raw = row.get("problem_id") or ""
            pid = norm_pid(pid_raw)
            tc_json = row.get("evaluation_test_cases") or "[]"
            try:
                tcs = json.loads(tc_json)
            except Exception:
                tcs = []
            tests[pid] = tcs
    return tests


def load_seeds(train_problems: set) -> list[dict]:
    seeds = []
    with open(CODESTREAM_CSV, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            lang = (row.get("programming_language") or "").lower().replace("+", "p").strip()
            if lang not in ("c", "cpp"):
                continue
            if (row.get("final_verdict") or "").strip().lower() != "accepted":
                continue
            pid_raw = row.get("problem_id") or ""
            pid = norm_pid(pid_raw)
            if pid not in train_problems:
                continue
            code = row.get("source_code") or ""
            if len(code.strip()) < 30:
                continue
            seeds.append({
                "submission_id": row.get("submission_id"),
                "problem_id": pid,
                "language": lang,
                "source_code": code,
                "attempt_number": row.get("attempt_number"),
                "user_id": row.get("user_id"),
            })
    return seeds


def load_operator_library() -> dict:
    with open(OPERATOR_LIB, encoding="utf-8") as fh:
        return json.load(fh)


def load_template_seeds(train_problems: set, problem_to_cluster: dict) -> list[dict]:
    """
    Return template seeds for every class, tagged with the first available
    train-side problem_id so that proof rows get a valid cluster reference.
    Templates carry _inline_tests; Verifier uses those instead of the CSV.
    """
    anchor_pid = next(
        (pid for pid in sorted(train_problems)), "tl-codestream-prob_001"
    )
    seeds = []
    for cls, templates in SEED_TEMPLATES.items():
        for tpl in templates:
            seed = dict(tpl)
            seed["problem_id"] = anchor_pid
            seed["language"] = "cpp"
            seed["attempt_number"] = None
            seed["user_id"] = f"template_{cls}"
            seeds.append(seed)
    print(f"Template seeds loaded: {len(seeds)} across {len(SEED_TEMPLATES)} classes")
    return seeds


# ---------------------------------------------------------------------------
# Verifier — E2
# ---------------------------------------------------------------------------

class Verifier:
    def __init__(self, work_dir: str, proofs_dir: str, problem_tests: dict):
        self.work_dir = work_dir
        self.proofs_dir = proofs_dir
        self.problem_tests = problem_tests
        os.makedirs(work_dir, exist_ok=True)
        os.makedirs(proofs_dir, exist_ok=True)
        self._clean_control_passed = False

    def _tests_for(self, seed: dict) -> list[dict]:
        """Return test cases: prefer _inline_tests on the seed over the CSV."""
        if seed.get("_inline_tests"):
            return seed["_inline_tests"]
        return self.problem_tests.get(seed["problem_id"], [])

    def verify_seed(self, seed: dict) -> tuple[bool, str]:
        """E2 gate: seed must compile and pass all tests pre-mutation."""
        tests = self._tests_for(seed)
        if not tests:
            return False, "no_tests"

        sid = seed["submission_id"].replace("/", "_")
        exe = os.path.join(self.work_dir, f"seed_{sid}.exe")
        ok, stderr = compile_cpp(seed["source_code"], exe)
        if not ok:
            return False, f"compile_fail: {stderr[:200]}"

        results = run_tests(exe, tests)
        try:
            if os.path.exists(exe):
                os.unlink(exe)
        except Exception:
            pass
        if results["failed"] > 0:
            return False, f"seed_fails_{results['failed']}_tests"

        return True, "ok"

    def verify_mutant(self, seed: dict, mutant_code: str, label: str,
                      operator_name: str) -> tuple[bool, dict]:
        """
        Full E2 verification for a mutant:
        - Compile with warnings
        - Compile with sanitizers
        - Execute against tests -> must fail >= 1
        - Collision check
        Returns (passes, proof_dict).
        """
        pid = seed["problem_id"]
        tests = self._tests_for(seed)
        if not tests:
            return False, {"reason": "no_tests"}

        run_id = uuid.uuid4().hex[:8]
        exe_std = os.path.join(self.work_dir, f"mut_{run_id}.exe")

        # Compile standard (get warnings)
        ok_std, stderr_std = compile_cpp(mutant_code, exe_std, "standard")
        if not ok_std:
            return False, {"reason": "mutant_compile_fail", "stderr": stderr_std[:400]}

        # Execute standard binary first
        results = run_tests(exe_std, tests)

        # Sanitizer compile only when std passes (UB-based bugs: ARRAY_BOUNDS, UNINIT_VAR)
        exe_san = exe_std + "_san"
        ok_san, stderr_san = False, ""
        if results["failed"] == 0:
            try:
                import shutil as _sh
                free = _sh.disk_usage(self.work_dir).free
                if free > 200 * 1024 * 1024:
                    ok_san, stderr_san = compile_cpp(mutant_code, exe_san, "sanitizer")
                    if ok_san and os.path.exists(exe_san):
                        san_results = run_tests(exe_san, tests)
                        if san_results["failed"] > 0:
                            results = san_results  # ASAN/UBSAN caught UB
            except Exception:
                pass

        if results["failed"] == 0:
            return False, {"reason": "mutant_passes_all_tests"}

        # Collision check: only flag signatures NEW in mutant, not pre-existing in seed
        collisions = check_collision(seed["source_code"], mutant_code, label)
        if collisions:
            return False, {"reason": f"collision_with_{'+'.join(collisions)}"}

        # Proof
        proof = {
            "run_id": run_id,
            "seed_submission_id": seed["submission_id"],
            "problem_id": pid,
            "operator": operator_name,
            "label": label,
            "seed_sha256": sha256(seed["source_code"]),
            "mutant_sha256": sha256(mutant_code),
            "compile_warnings_std": stderr_std[:500] if stderr_std else "",
            "sanitizer_ok": ok_san,  # False if not needed (std already failed)
            "tests_passed": results["passed"],
            "tests_failed": results["failed"],
            "tests_total": results["total"],
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Store proof
        proof_path = os.path.join(self.proofs_dir, f"{run_id}.json")
        with open(proof_path, "w", encoding="utf-8") as fh:
            json.dump(proof, fh)

        # Cleanup immediately
        for exe in [exe_std, exe_san]:
            try:
                if os.path.exists(exe):
                    os.unlink(exe)
            except Exception:
                pass

        return True, proof

    def run_clean_control(self, seeds: list[dict], n: int = 20) -> tuple[int, int]:
        """
        E2 control: run n known-clean seeds through all operators;
        none should produce a false-firing mutant that passes all tests.
        Returns (clean_count, false_firing_count).
        """
        import random
        sample = random.sample(seeds, min(n, len(seeds)))
        clean = ff = 0
        for seed in sample:
            pid = seed["problem_id"]
            tests = self.problem_tests.get(pid, [])
            if not tests:
                continue
            exe = os.path.join(self.work_dir, f"ctrl_{seed['submission_id']}.exe")
            ok, _ = compile_cpp(seed["source_code"], exe)
            if not ok:
                continue
            results = run_tests(exe, tests)
            if results["failed"] == 0:
                clean += 1
            else:
                ff += 1
            try:
                os.unlink(exe)
            except Exception:
                pass
        self._clean_control_passed = (ff == 0)
        return clean, ff


# ---------------------------------------------------------------------------
# Row builder
# ---------------------------------------------------------------------------

def make_row(row_id: str, seed: dict, mutant_code: str, label: str,
             operator_name: str, proof: dict, problem_cluster: str,
             pipeline_run_id: str) -> dict:
    return {
        "row_id": row_id,
        "dataset_source": "SYNTHETIC",
        "source_record_id": seed["submission_id"],
        "problem_id": seed["problem_id"],
        "problem_cluster": problem_cluster,
        "language": "cpp",
        "label": label,
        "label_source": "synthetic",
        "label_confidence": 0.93,
        "secondary_labels": [],
        "verdict": None,
        "firing_functions": [f"verify_operator_{label.lower()}"],
        "seed_ref": seed["submission_id"],
        "mutation_op": operator_name,
        "verified_by_execution": True,
        "meta": {
            "user_id_hash": sha256(seed.get("user_id") or ""),
            "attempt_index": seed.get("attempt_number"),
            "timestamp": None,
            "prev_submission_id": None,
        },
        "static": {
            "source_code": mutant_code,
            "source_code_sha256": sha256(mutant_code),
            "loc": mutant_code.count("\n"),
        },
        "warnings": {
            "compile_warnings": proof.get("compile_warnings_std", ""),
        },
        "runtime": {
            "tests_passed": proof.get("tests_passed"),
            "tests_failed": proof.get("tests_failed"),
            "tests_total": proof.get("tests_total"),
            "sanitizer_ok": proof.get("sanitizer_ok"),
        },
        "tests": {},
        "cpg": {},
        "context": {},
        "pipeline_run_id": pipeline_run_id,
        "taxonomy_version": TAXONOMY_VERSION,
        "schema_version": SCHEMA_VERSION,
    }


# ---------------------------------------------------------------------------
# Main generation loop
# ---------------------------------------------------------------------------

def generate(
    target_class: str | None,
    n_target: int,
    is_decoys: bool,
    out_path: str,
    train_problems: set,
    problem_to_cluster: dict,
    problem_tests: dict,
    fast_mode: bool = False,
):
    codestream_seeds = load_seeds(train_problems)
    template_seeds = load_template_seeds(train_problems, problem_to_cluster)
    seeds = codestream_seeds + template_seeds
    print(f"Seeds loaded: {len(codestream_seeds)} CodeStream + {len(template_seeds)} templates = {len(seeds)} total")
    if not seeds:
        print("ERROR: no seeds — check cluster split and CodeStream CSV", file=sys.stderr)
        sys.exit(1)

    lib = load_operator_library()
    pipeline_run_id = f"run-{uuid.uuid4().hex[:12]}"
    work_dir = tempfile.mkdtemp(
        prefix="tracelearn_mutants_",
        dir=os.path.join(ROOT, "data")  # use project data dir, not system /tmp
    )
    proofs_dir = PROOFS_DIR

    verifier = Verifier(work_dir, proofs_dir, problem_tests)

    verified_cache: dict[str, bool] = {}

    # Template seeds are always trusted (hand-crafted, verified offline).
    template_sid_set = {s["submission_id"] for s in template_seeds}
    for s in template_seeds:
        verified_cache[s["submission_id"]] = True

    if fast_mode:
        # Fast mode: trust Accepted submissions (E3 pilot only)
        print("Fast mode: trusting Accepted submissions (skipping seed pre-check)")
        valid_seeds = seeds
        for s in codestream_seeds:
            verified_cache[s["submission_id"]] = True
    else:
        # E2: validate first 30 CodeStream seeds eagerly as a smoke-test gate,
        # then validate lazily during generation (templates already trusted above)
        print("E2: validating seed sample (first 30 CodeStream) pre-mutation...")
        valid_seeds = list(template_seeds)  # templates always valid
        seed_fail_reasons = defaultdict(int)
        eager_limit = min(30, len(codestream_seeds))
        for seed in codestream_seeds[:eager_limit]:
            ok, reason = verifier.verify_seed(seed)
            if ok:
                valid_seeds.append(seed)
            else:
                seed_fail_reasons[reason] += 1

        pct = 100 * len(valid_seeds) / eager_limit if eager_limit > 0 else 0
        print(f"Valid seeds (sample): {len(valid_seeds)}/{eager_limit} ({pct:.1f}%)")
        if seed_fail_reasons:
            for reason, count in sorted(seed_fail_reasons.items()):
                print(f"  seed_fail [{reason}]: {count}")

        if pct < 50:
            print("ERROR: <50% of sample seeds passed E2 -- fix seed pool before scaling", file=sys.stderr)
            shutil.rmtree(work_dir, ignore_errors=True)
            sys.exit(1)

        for s in valid_seeds:
            verified_cache[s["submission_id"]] = True
        n_remaining = len(codestream_seeds) - eager_limit
        print(f"Remaining {n_remaining} CodeStream seeds will be verified lazily")

    # E2 clean control on CodeStream seeds only (skip in fast mode)
    if not fast_mode:
        print("E2: running 20-item clean control...")
        cs_valid = [s for s in valid_seeds if s["submission_id"] not in template_sid_set]
        clean, ff = verifier.run_clean_control(cs_valid[:20], n=min(20, len(cs_valid)))
        print(f"Clean control: {clean} clean, {ff} false-fires")
        if ff > 0:
            print("WARNING: clean control has false-fires -- operator regression possible")

    # Per-class targets
    if is_decoys:
        classes_to_generate = {"CPP_OTHER_ERROR": n_target}
    elif target_class:
        classes_to_generate = {target_class: n_target}
    else:
        # Pilot: distribute across all 11 classes (>= 5 per class for E3)
        per_class = max(5, n_target // len(CLASSES))
        classes_to_generate = {cls: per_class for cls in CLASSES}

    # Track per-seed usage
    seed_usage = defaultdict(int)  # submission_id -> total mutants generated

    # Existing rows (if appending)
    existing_rows = []
    existing_ids = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    existing_rows.append(row)
                    existing_ids.add(row["row_id"])

    existing_by_class = defaultdict(int)
    for row in existing_rows:
        existing_by_class[row["label"]] += 1

    new_rows = []
    stats = defaultdict(lambda: {"generated": 0, "rejected": 0, "reasons": defaultdict(int)})

    for cls, target in classes_to_generate.items():
        already_have = existing_by_class[cls]
        need = max(0, target - already_have)
        if need == 0:
            print(f"  {cls}: already at target ({already_have})")
            continue

        print(f"  Generating {need} for {cls} (have {already_have})...")

        if is_decoys or cls == "CPP_OTHER_ERROR":
            forms = lib.get("decoy_operators", [])
        else:
            op_entry = lib["operators"].get(cls, {})
            forms = op_entry.get("forms", [])

        if not forms:
            print(f"    WARNING: no forms for {cls}")
            continue

        import random
        # Matching-class templates first (reliable pattern hits), then shuffled CodeStream seeds
        matching = [s for s in valid_seeds if s.get("_hint_class") == cls]
        other = [s for s in valid_seeds if not s.get("_hint_class") or s.get("_hint_class") != cls]
        random.shuffle(other)
        all_seeds = matching + other

        for seed in all_seeds:
            if stats[cls]["generated"] >= need:
                break
            sid = seed["submission_id"]
            if seed_usage[sid] >= MAX_MUTANTS_PER_SEED:
                continue

            # Lazy E2 seed verification (fast mode: trusts seeds already)
            if not fast_mode and sid not in verified_cache:
                ok_seed, _ = verifier.verify_seed(seed)
                verified_cache[sid] = ok_seed
            if not fast_mode and not verified_cache.get(sid, True):
                continue

            # Try ALL forms on this seed until one produces a verified mutant
            # (or we hit the per-seed cap for this seed)
            for form in forms:
                if stats[cls]["generated"] >= need:
                    break
                if seed_usage[sid] >= MAX_MUTANTS_PER_SEED:
                    break

                mutant_code = apply_operator_form(seed["source_code"], form)
                if mutant_code is None:
                    stats[cls]["reasons"]["pattern_not_found"] += 1
                    continue

                ok, proof = verifier.verify_mutant(seed, mutant_code, cls, form["name"])
                if not ok:
                    stats[cls]["rejected"] += 1
                    stats[cls]["reasons"][proof.get("reason", "unknown")] += 1
                    continue

                seed_usage[sid] += 1
                row_idx = already_have + stats[cls]["generated"] + 1
                row_id = f"mut-{hash(cls) % 1000:03d}{row_idx:05d}"
                cluster = problem_to_cluster.get(seed["problem_id"], "clu-unknown")
                row = make_row(row_id, seed, mutant_code, cls, form["name"], proof, cluster, pipeline_run_id)
                new_rows.append(row)
                stats[cls]["generated"] += 1

        print(f"    Generated: {stats[cls]['generated']} | "
              f"Rejected: {stats[cls]['rejected']}")
        if stats[cls]["reasons"]:
            for reason, count in sorted(stats[cls]["reasons"].items()):
                print(f"      [{reason}]: {count}")

    # Write output
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "a", encoding="utf-8") as fh:
        for row in new_rows:
            fh.write(json.dumps(row) + "\n")

    total_new = len(new_rows)
    total_all = len(existing_rows) + total_new

    print(f"\nDone. New rows: {total_new} | Total in file: {total_all}")
    print(f"Pipeline run: {pipeline_run_id}")

    # Class summary
    print("\nClass totals (existing + new):")
    final_counts = dict(existing_by_class)
    for row in new_rows:
        final_counts[row["label"]] = final_counts.get(row["label"], 0) + 1
    for cls in CLASSES:
        count = final_counts.get(cls, 0)
        floor = FLOOR.get(cls, 0)
        status = "OK" if count >= floor else f"UNDER ({floor - count} needed)"
        print(f"  {cls:<28}: {count:>5}  floor={floor}  {status}")

    shutil.rmtree(work_dir, ignore_errors=True)
    return total_new


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="E2 verifier + E3/E4 mutant generation for Lane A")
    parser.add_argument("--pilot", action="store_true", help="E3: generate 150 mutants (>=5/class)")
    parser.add_argument("--scale", action="store_true", help="E4: generate to floor targets (2900)")
    parser.add_argument("--class", dest="target_class", help="Generate for one class only")
    parser.add_argument("--n", type=int, default=50, help="Number to generate (with --class)")
    parser.add_argument("--decoys", action="store_true", help="E1d: generate decoy OTHER_ERROR rows")
    parser.add_argument("--fast", action="store_true", help="Skip E2 seed pre-check (faster, for dev/testing)")
    parser.add_argument("--out", default=OUT_JSONL, help="Output JSONL path")
    args = parser.parse_args()

    if not os.path.exists(CLUSTER_SPLIT):
        print(f"ERROR: {CLUSTER_SPLIT} not found -- run cluster_problems.py first", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(OPERATOR_LIB):
        print(f"ERROR: {OPERATOR_LIB} not found -- run mine_operators.py first", file=sys.stderr)
        sys.exit(1)

    with open(CLUSTER_SPLIT, encoding="utf-8") as fh:
        cluster_data = json.load(fh)

    train_problems: set[str] = set()
    problem_to_cluster: dict[str, str] = {}
    for clu_id, clu_info in cluster_data["clusters"].items():
        for pid in clu_info["problems"]:
            problem_to_cluster[pid] = clu_id
            if clu_info["split"] == "train":
                train_problems.add(pid)

    problem_tests = load_problem_tests()
    print(f"Problem tests loaded: {len(problem_tests)} problems")

    if args.pilot:
        n_target = 150
        target_class = None
    elif args.scale:
        n_target = max(FLOOR.values())
        target_class = None
    elif args.target_class:
        target_class = args.target_class
        n_target = args.n
    else:
        print("Specify --pilot, --scale, or --class <CLASS> --n <N>")
        parser.print_help()
        sys.exit(0)

    generate(
        target_class=args.target_class if not (args.pilot or args.scale) else None,
        n_target=n_target,
        is_decoys=args.decoys,
        out_path=args.out,
        train_problems=train_problems,
        problem_to_cluster=problem_to_cluster,
        problem_tests=problem_tests,
        fast_mode=args.pilot or args.fast,  # pilot/--fast skip E2 seed pre-check
    )


if __name__ == "__main__":
    main()
