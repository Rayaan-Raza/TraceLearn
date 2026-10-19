#!/usr/bin/env python3
"""Problem clustering + cluster split (master plan §13.4, R-I4).

Week-0 dependency that unblocks Eman's train-side reverse-mutation mining:
cluster CodeStream problems by TF-IDF statement cosine > 0.8, then split whole
clusters into train-side / dev-gold / test-side.

Binding rules (§13.4):
- clusters, not raw problems, since TF-IDF clustering shrinks the count;
- full split budget: train >=21, dev-gold 5, test 15 (needs >=41 clusters);
- fallback when clustering yields too few: dev-gold 4, test 12 (gold spans
  >=10), the 150 floor protected first;
- clusters split only as a unit — a test-side cluster's problems (and any
  mutant seeded from them) never reach training;
- clustering is deterministic (same statements -> same clusters + split).

Clustering is single-linkage: two problems are linked when cosine > 0.8, and a
cluster is a connected component of that link graph. Single-linkage is the
leakage-safe grouping — a near-duplicate family (p1~p2~p3 even if p1!p3) can
never straddle train and test.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_PROBLEMS_CSV = (
    ROOT / "data" / "Data_from_Datasets" / "intermediate" / "normalized"
    / "problems" / "problems.csv"
)
DEFAULT_OUT = (
    ROOT / "data" / "misconception_dataset" / "splits" / "cluster_assignments.csv"
)

COSINE_THRESHOLD = 0.8  # §13.4 "TF-IDF statement cosine > 0.8"

# §13.4 split budget: (train_min, dev_gold, test) and whether it is fallback.
_FULL_BUDGET = (21, 5, 15)
_FALLBACK_BUDGET = (21, 4, 12)
_FULL_MIN_CLUSTERS = sum(_FULL_BUDGET[1:]) + _FULL_BUDGET[0]  # 5 + 15 + 21 = 41


# ------------------------------------------------- connected components


class _UnionFind:
    def __init__(self, n: int) -> None:
        self._parent = list(range(n))

    def find(self, x: int) -> int:
        parent = self._parent
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path compression
            x = parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra


def clusters_from_similarity(
    ids: Sequence[str], sim: Sequence[Sequence[float]], threshold: float = COSINE_THRESHOLD
) -> dict[str, str]:
    """Single-linkage clusters from a cosine similarity matrix.

    Link when sim[i][j] > threshold (strictly greater, per §13.4). Returns
    {problem_id: cluster_id}; cluster ids are `clu-NNN` assigned in sorted order
    of each cluster's smallest member id, so the result is independent of the
    input order.
    """
    if len(ids) != len(sim):
        raise ValueError("ids and sim must be the same length")
    n = len(ids)
    if n == 0:
        return {}

    uf = _UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            if sim[i][j] > threshold:
                uf.union(i, j)

    # group indices by component root
    groups: dict[int, list[str]] = {}
    for idx, pid in enumerate(ids):
        groups.setdefault(uf.find(idx), []).append(pid)

    # order components by their smallest member id -> deterministic clu ids
    ordered = sorted(groups.values(), key=lambda members: min(members))
    return {
        pid: f"clu-{rank:03d}"
        for rank, members in enumerate(ordered)
        for pid in members
    }


# ----------------------------------------------------------- TF-IDF pass


def cluster_problems(
    statements: dict[str, str], threshold: float = COSINE_THRESHOLD
) -> dict[str, str]:
    """Cluster problems by TF-IDF statement cosine > threshold.

    A blank/whitespace-only statement gets a zero vector, so it links to nothing
    and stands as its own cluster. An all-blank corpus (or empty input) yields
    all-singleton clusters without invoking the vectorizer.
    """
    if not statements:
        return {}
    ids = sorted(statements)
    texts = [statements[pid] or "" for pid in ids]

    if not any(t.strip() for t in texts):
        return {pid: f"clu-{rank:03d}" for rank, pid in enumerate(ids)}

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vectorizer = TfidfVectorizer()
    try:
        matrix = vectorizer.fit_transform(texts)
    except ValueError:
        # empty vocabulary (e.g. only stop-word tokens) -> all singletons
        return {pid: f"clu-{rank:03d}" for rank, pid in enumerate(ids)}

    sim = cosine_similarity(matrix)
    return clusters_from_similarity(ids, sim, threshold=threshold)


# ---------------------------------------------------------- split budget


def split_budget(n_clusters: int) -> tuple[int, int, int, bool]:
    """(train_min, dev_gold, test, is_fallback) for a cluster count.

    The full 21+5+15=41 budget needs >=41 clusters. Below that the reduced
    fallback budget (dev-gold 4, test 12) is used: it is always feasible and
    keeps more clusters on the train side, protecting the 150 floor first.
    """
    if n_clusters >= _FULL_MIN_CLUSTERS:
        train_min, dev, test = _FULL_BUDGET
        return train_min, dev, test, False
    train_min, dev, test = _FALLBACK_BUDGET
    return train_min, dev, test, True


def assign_splits(
    cluster_ids: Iterable[str], seed: int = 13
) -> tuple[dict[str, str], bool]:
    """Assign whole clusters to test / dev_gold / train. Deterministic per seed.

    Returns ({cluster_id: split}, is_fallback). Test and dev-gold are carved out
    first from a seeded shuffle; every remaining cluster is train (which absorbs
    extras beyond the train floor). When the total is too low to give train its
    floor, train shrinks — a warning for the caller, never a hard failure, since
    the gold/test floor is what must be protected (§13.4).
    """
    import random

    cids = sorted(set(cluster_ids))
    _, dev, test, fallback = split_budget(len(cids))

    shuffled = list(cids)
    random.Random(seed).shuffle(shuffled)

    splits: dict[str, str] = {}
    for rank, cid in enumerate(shuffled):
        if rank < test:
            splits[cid] = "test"
        elif rank < test + dev:
            splits[cid] = "dev_gold"
        else:
            splits[cid] = "train"
    return splits, fallback


# ------------------------------------------------------------------ CLI


def build_assignments(
    statements: dict[str, str], seed: int = 13
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Cluster + split, returning row dicts and a summary."""
    clusters = cluster_problems(statements)
    cids = sorted(set(clusters.values()))
    splits, fallback = assign_splits(cids, seed=seed)

    rows: list[dict[str, Any]] = []
    for pid in sorted(statements):
        cid = clusters[pid]
        rows.append(
            {
                "problem_id": pid,
                "cluster_id": cid,
                "split": splits[cid],
                "statement_len": len(statements[pid] or ""),
            }
        )

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["split"]] = counts.get(row["split"], 0) + 1
    summary = {
        "n_problems": len(statements),
        "n_clusters": len(cids),
        "fallback": fallback,
        "problem_counts": counts,
        "cluster_counts": {
            s: sum(1 for cid in cids if splits[cid] == s) for s in ("train", "dev_gold", "test")
        },
    }
    return rows, summary


def _load_codestream_statements(problems_csv: Path) -> dict[str, str]:
    stmts: dict[str, str] = {}
    with problems_csv.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("dataset_source") == "CODESTREAM":
                stmts[row["problem_id"]] = row.get("statement") or row.get("title") or ""
    return stmts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--problems-csv", type=Path, default=DEFAULT_PROBLEMS_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args(argv)

    if not args.problems_csv.is_file():
        print(f"FAIL  problems.csv not found: {args.problems_csv}")
        return 1

    statements = _load_codestream_statements(args.problems_csv)
    if not statements:
        print("FAIL  no CODESTREAM problems found to cluster")
        return 1

    rows, summary = build_assignments(statements, seed=args.seed)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["problem_id", "cluster_id", "split", "statement_len"]
        )
        writer.writeheader()
        writer.writerows(rows)

    mode = "fallback" if summary["fallback"] else "full"
    print(f"clustered {summary['n_problems']} CODESTREAM problems into {summary['n_clusters']} clusters ({mode} budget)")
    print(f"  cluster split: {summary['cluster_counts']}")
    print(f"  problem split: {summary['problem_counts']}")
    print(f"wrote {args.out}")
    if summary["cluster_counts"]["train"] < 21:
        print(f"  WARNING: train-side clusters ({summary['cluster_counts']['train']}) below the 21 floor — gold/test floor protected first (§13.4)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
