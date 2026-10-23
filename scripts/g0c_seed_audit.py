"""
g0c_seed_audit.py — Gate G0c: count viable seeds per tl-cpp-v2 class
before committing to floor targets (§9.0-G0c).

Seeds = CodeStream Accepted C/C++ submissions on TRAIN-SIDE clusters only.
Each seed will receive at most 3 mutants (5 if class is seed-starved after audit).

Per-class viability: a seed is 'viable' for a class if the problem's test suite
can distinguish the operator's effect (heuristic flag based on test count + type).

Outputs:
  data/misconception_dataset/raw_recovery/g0c_seed_audit.json

Usage:
  python scripts/g0c_seed_audit.py
"""

import json
import os
import sys
from collections import defaultdict

import csv
csv.field_size_limit(10 ** 7)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODESTREAM_CSV = os.path.join(
    ROOT, "Datasets_RAW",
    "CodeStream A Dataset of Iterative Programming Subm",
    "Submission Data.csv",
)
PROBLEMS_JSONL = os.path.join(ROOT, "data", "intermediate", "normalized", "problems", "problems.jsonl")
CLUSTER_SPLIT = os.path.join(ROOT, "data", "misconception_dataset", "raw_recovery", "cluster_split.json")
OUT_DIR = os.path.join(ROOT, "data", "misconception_dataset", "raw_recovery")

# Raw CSV uses short IDs (prob_006); normalized uses tl-codestream-prob_006
def normalize_problem_id(raw_id: str) -> str:
    if raw_id.startswith("tl-"):
        return raw_id
    return f"tl-codestream-{raw_id}"

# tl-cpp-v2 classes (11 modeled)
CLASSES = [
    "CPP_LOOP_BOUNDARY",
    "CPP_OFF_BY_ONE",
    "CPP_ARRAY_BOUNDS",
    "CPP_UNINITIALIZED_VAR",
    "CPP_INT_OVERFLOW",
    "CPP_MISSING_BASE_CASE",
    "CPP_ASSIGN_VS_COMPARE",
    "CPP_WRONG_LOOP_DIR",
    "CPP_RANGE_CHECK",
    "CPP_STALE_EXIT",
    "CPP_OTHER_ERROR",
]

# Floor per class from §8
FLOOR = {
    "CPP_LOOP_BOUNDARY": 300,
    "CPP_OFF_BY_ONE": 300,
    "CPP_ARRAY_BOUNDS": 300,
    "CPP_UNINITIALIZED_VAR": 300,
    "CPP_INT_OVERFLOW": 300,
    "CPP_MISSING_BASE_CASE": 300,
    "CPP_ASSIGN_VS_COMPARE": 300,
    "CPP_WRONG_LOOP_DIR": 200,
    "CPP_RANGE_CHECK": 200,
    "CPP_STALE_EXIT": 200,
    "CPP_OTHER_ERROR": 200,
}

# Mutants per seed cap (relaxable to 5 after G0c for seed-starved classes)
BASE_CAP = 3
RELAXED_CAP = 5
STARVED_THRESHOLD_RATIO = 0.8  # if estimated_mutants < 0.8 * floor -> seed-starved


def load_cluster_split(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_accepted_cpp_seeds(csv_path: str, train_problems: set) -> list:
    seeds = []
    with open(csv_path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            lang = (row.get("programming_language") or "").lower().replace("+", "p").replace(" ", "")
            if lang not in ("c", "cpp"):
                continue
            verdict = (row.get("final_verdict") or "").strip().lower()
            if verdict != "accepted":
                continue
            raw_pid = row.get("problem_id") or ""
            pid = normalize_problem_id(raw_pid)
            if pid not in train_problems:
                continue
            code = row.get("source_code") or ""
            if len(code.strip()) < 20:
                continue
            seeds.append({
                "submission_id": row.get("submission_id"),
                "problem_id": pid,
                "language": lang,
                "source_code": code,
                "attempt_order": row.get("attempt_number"),
            })
    return seeds


def estimate_class_viability(seeds: list, problem_test_counts: dict) -> dict:
    """
    Heuristic: a seed is viable for a class based on whether the problem
    has enough test cases to catch the operator's effect.

    Classes that need boundary tests need ≥2 test cases.
    Classes that need overflow tests need ≥1 test with large input.
    Hard-3 classes (8,9,10) need ≥3 test cases.
    """
    problem_ids = set(s["problem_id"] for s in seeds)

    class_viable_seeds = defaultdict(set)
    for s in seeds:
        pid = s["problem_id"]
        n_tests = problem_test_counts.get(pid, 0)
        sid = s["submission_id"]

        # Classes with boundary sensitivity
        if n_tests >= 2:
            class_viable_seeds["CPP_LOOP_BOUNDARY"].add(sid)
            class_viable_seeds["CPP_OFF_BY_ONE"].add(sid)
            class_viable_seeds["CPP_ARRAY_BOUNDS"].add(sid)
            class_viable_seeds["CPP_INT_OVERFLOW"].add(sid)
            class_viable_seeds["CPP_ASSIGN_VS_COMPARE"].add(sid)
            class_viable_seeds["CPP_OTHER_ERROR"].add(sid)

        if n_tests >= 1:
            class_viable_seeds["CPP_UNINITIALIZED_VAR"].add(sid)
            class_viable_seeds["CPP_MISSING_BASE_CASE"].add(sid)

        # Hard-3: need more tests to distinguish subtle ordering/range issues
        if n_tests >= 3:
            class_viable_seeds["CPP_WRONG_LOOP_DIR"].add(sid)
            class_viable_seeds["CPP_RANGE_CHECK"].add(sid)
            class_viable_seeds["CPP_STALE_EXIT"].add(sid)

    return {cls: list(sids) for cls, sids in class_viable_seeds.items()}


def main():
    if not os.path.exists(CLUSTER_SPLIT):
        print(f"ERROR: {CLUSTER_SPLIT} not found -- run cluster_problems.py first", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(CODESTREAM_CSV):
        print(f"ERROR: {CODESTREAM_CSV} not found", file=sys.stderr)
        sys.exit(1)

    cluster_data = load_cluster_split(CLUSTER_SPLIT)
    problem_to_cluster = cluster_data["problem_to_cluster"]
    clusters = cluster_data["clusters"]

    # Build train-side problem set
    train_problems = set()
    for clu_id, clu_info in clusters.items():
        if clu_info["split"] == "train":
            for pid in clu_info["problems"]:
                train_problems.add(pid)

    print(f"Train-side problems: {len(train_problems)}")
    print(f"Train clusters: {sum(1 for c in clusters.values() if c['split'] == 'train')}")

    # Load problem test counts from normalized problems
    problems_path = PROBLEMS_JSONL
    problem_test_counts = {}
    with open(problems_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            pid = row.get("problem_id")
            tests = row.get("sample_tests") or row.get("test_cases") or []
            if isinstance(tests, str):
                try:
                    tests = json.loads(tests)
                except Exception:
                    tests = []
            problem_test_counts[pid] = len(tests) if isinstance(tests, list) else 0

    # Load seeds
    seeds = load_accepted_cpp_seeds(CODESTREAM_CSV, train_problems)
    print(f"\nAccepted C/C++ seeds on train-side: {len(seeds)}")

    # Per-problem seed count
    seeds_by_problem = defaultdict(list)
    for s in seeds:
        seeds_by_problem[s["problem_id"]].append(s["submission_id"])

    # Per-class viability
    class_viable = estimate_class_viability(seeds, problem_test_counts)

    # Estimate mutants per class
    print("\nG0c per-class seed audit:")
    print(f"{'Class':<28} {'Viable seeds':>13} {'Max mutants(@3)':>15} {'Floor':>6} {'Status':>12}")
    print("-" * 80)

    class_audit = {}
    for cls in CLASSES:
        viable = class_viable.get(cls, [])
        n_viable = len(viable)
        max_mutants = n_viable * BASE_CAP
        floor = FLOOR[cls]
        ratio = max_mutants / floor if floor > 0 else 1.0
        if ratio < STARVED_THRESHOLD_RATIO:
            status = "SEED-STARVED"
            cap = RELAXED_CAP
            max_relaxed = n_viable * cap
        else:
            status = "OK"
            cap = BASE_CAP
            max_relaxed = max_mutants

        print(f"  {cls:<26} {n_viable:>13} {max_mutants:>15} {floor:>6}  {status}")
        class_audit[cls] = {
            "viable_seeds": n_viable,
            "max_mutants_cap3": max_mutants,
            "max_mutants_cap5": n_viable * RELAXED_CAP,
            "floor": floor,
            "recommended_cap": cap,
            "status": status,
        }

    print()

    # Overall
    total_seeds = len(seeds)
    print(f"Total viable seeds (all classes use same pool): {total_seeds}")
    print(f"Max total mutants at cap=3: {total_seeds * BASE_CAP}")
    print(f"Max total mutants at cap=5: {total_seeds * RELAXED_CAP}")

    # Cluster spread per seed
    cluster_to_seeds = defaultdict(list)
    for s in seeds:
        clu = problem_to_cluster.get(s["problem_id"])
        if clu:
            cluster_to_seeds[clu].append(s["submission_id"])

    print(f"\nTrain clusters with seeds: {len(cluster_to_seeds)}")

    # Build output
    audit = {
        "created": "2026-10-21",
        "creator": "eman06",
        "script": "scripts/g0c_seed_audit.py",
        "cluster_split_ref": CLUSTER_SPLIT,
        "train_problems": sorted(train_problems),
        "train_clusters": sum(1 for c in clusters.values() if c["split"] == "train"),
        "total_accepted_cpp_seeds": total_seeds,
        "seeds_by_problem": {pid: len(sids) for pid, sids in seeds_by_problem.items()},
        "seeds_by_cluster": {clu: len(sids) for clu, sids in cluster_to_seeds.items()},
        "class_audit": class_audit,
        "notes": [
            "39 clusters from 46 problems at TF-IDF threshold 0.8",
            "19 train clusters (2 below >=21 guideline) — logged per §9.0-G0c",
            "All CodeStream Accepted C/C++ subs on train-side used as seed pool",
            "Seed-starved classes get cap relaxed to 5 per §9.0-G0c rules",
            "Hard-written seed templates allowed for any class with <150 viable seeds",
        ],
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "g0c_seed_audit.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(audit, fh, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
