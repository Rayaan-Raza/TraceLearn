"""
cluster_problems.py — Week 0 prerequisite for Lane A mining.

Clusters the 46 CodeStream problems by TF-IDF statement cosine similarity
(threshold > 0.8) and assigns each cluster to train / dev-gold / test split.

Split budget (§13.4):
  train: ≥21 clusters  dev-gold: 5 clusters  test: 15 clusters
  Total target: 41 clusters (46 problems spread across them)

Outputs:
  data/misconception_dataset/raw_recovery/cluster_split.json
  data/misconception_dataset/raw_recovery/problem_cluster_map.csv

Usage:
  python scripts/cluster_problems.py
  python scripts/cluster_problems.py --threshold 0.8 --seed 42
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict

# ---------------------------------------------------------------------------
# Optional sklearn import — graceful degradation if not installed
# ---------------------------------------------------------------------------
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBLEMS_JSONL = os.path.join(ROOT, "data", "intermediate", "normalized", "problems", "problems.jsonl")
OUT_DIR = os.path.join(ROOT, "data", "misconception_dataset", "raw_recovery")


def load_codestream_problems(path: str):
    """Return list of {problem_id, statement} for CodeStream problems only."""
    problems = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("dataset_source") != "CODESTREAM":
                continue
            stmt = row.get("statement") or row.get("statement_text") or ""
            problems.append({
                "problem_id": row["problem_id"],
                "statement": stmt,
            })
    return problems


def cluster_by_cosine(problems, threshold: float):
    """
    Union-Find clustering: two problems in the same cluster if cosine > threshold.
    Returns {problem_id: cluster_id}.
    """
    n = len(problems)
    statements = [p["statement"] for p in problems]

    vec = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
        sublinear_tf=True,
    )
    tfidf = vec.fit_transform(statements)
    sim = cosine_similarity(tfidf)

    # Union-Find
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if sim[i, j] > threshold:
                union(i, j)

    # Normalise to sequential cluster IDs
    root_to_clu = {}
    mapping = {}
    for i, p in enumerate(problems):
        r = find(i)
        if r not in root_to_clu:
            root_to_clu[r] = f"clu-{len(root_to_clu) + 1:03d}"
        mapping[p["problem_id"]] = root_to_clu[r]

    return mapping


def assign_splits(cluster_ids: list[str], seed: int, budget: dict):
    """
    Deterministic assignment of cluster IDs to train/dev-gold/test.

    budget = {"test": 15, "dev_gold": 5, "train": remainder}
    """
    rng = np.random.default_rng(seed)
    shuffled = list(cluster_ids)
    rng.shuffle(shuffled)

    n_test = budget.get("test", 15)
    n_dev = budget.get("dev_gold", 5)

    split = {}
    for i, clu in enumerate(shuffled):
        if i < n_test:
            split[clu] = "test"
        elif i < n_test + n_dev:
            split[clu] = "dev_gold"
        else:
            split[clu] = "train"

    return split


def main(threshold: float, seed: int):
    if not SKLEARN_OK:
        print("ERROR: scikit-learn is required.  pip install scikit-learn", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(PROBLEMS_JSONL):
        print(f"ERROR: {PROBLEMS_JSONL} not found — run ingest_sources.py first", file=sys.stderr)
        sys.exit(1)

    problems = load_codestream_problems(PROBLEMS_JSONL)
    print(f"Loaded {len(problems)} CodeStream problems")

    if len(problems) < 2:
        print("ERROR: need ≥2 problems to cluster", file=sys.stderr)
        sys.exit(1)

    problem_to_cluster = cluster_by_cosine(problems, threshold)

    # Cluster stats
    cluster_to_problems = defaultdict(list)
    for pid, clu in problem_to_cluster.items():
        cluster_to_problems[clu].append(pid)

    n_clusters = len(cluster_to_problems)
    print(f"Clusters at threshold {threshold}: {n_clusters}")
    for clu, pids in sorted(cluster_to_problems.items()):
        print(f"  {clu}: {len(pids)} problems — {pids}")

    # Split assignment
    all_cluster_ids = sorted(cluster_to_problems.keys())
    split_map = assign_splits(all_cluster_ids, seed, {"test": 15, "dev_gold": 5})

    split_counts = defaultdict(int)
    for clu, sp in split_map.items():
        split_counts[sp] += 1
    print("\nCluster -> split:")
    for sp, count in sorted(split_counts.items()):
        print(f"  {sp}: {count} clusters")

    # Build output
    cluster_split = {
        "created": "2026-10-21",
        "creator": "eman06",
        "script": "scripts/cluster_problems.py",
        "threshold": threshold,
        "seed": seed,
        "n_problems": len(problems),
        "n_clusters": n_clusters,
        "split_counts": dict(split_counts),
        "clusters": {
            clu: {
                "problems": cluster_to_problems[clu],
                "split": split_map[clu],
            }
            for clu in all_cluster_ids
        },
        "problem_to_cluster": problem_to_cluster,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    split_path = os.path.join(OUT_DIR, "cluster_split.json")
    with open(split_path, "w", encoding="utf-8") as fh:
        json.dump(cluster_split, fh, indent=2)
    print(f"\nWrote {split_path}")

    # CSV for quick inspection
    csv_path = os.path.join(OUT_DIR, "problem_cluster_map.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["problem_id", "problem_cluster", "split"])
        writer.writeheader()
        for p in sorted(problems, key=lambda x: x["problem_id"]):
            pid = p["problem_id"]
            clu = problem_to_cluster[pid]
            writer.writerow({
                "problem_id": pid,
                "problem_cluster": clu,
                "split": split_map[clu],
            })
    print(f"Wrote {csv_path}")

    # Validation
    train_clusters = [c for c, s in split_map.items() if s == "train"]
    print(f"\nValidation: train clusters = {len(train_clusters)} (need >=21)")
    if len(train_clusters) < 21:
        print("WARNING: fewer than 21 train clusters — E1 mining pool is small")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cluster CodeStream problems for train/dev-gold/test split")
    parser.add_argument("--threshold", type=float, default=0.8,
                        help="TF-IDF cosine similarity threshold (default 0.8)")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for split assignment (default 42)")
    args = parser.parse_args()
    main(args.threshold, args.seed)
