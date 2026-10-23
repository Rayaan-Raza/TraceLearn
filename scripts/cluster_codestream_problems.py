"""Week-0 CodeStream problem clustering and the train / dev-gold / test cluster split.

Master Plan §7 (leakage control) and §13.4 (the 46-problem budget):

* TF-IDF over problem statements, cosine > 0.8 joins two problems; clusters are
  the connected components (single link), so near-duplicate statements always
  share a cluster.
* Clusters are assigned to pools as a unit: train ≥21 / dev-gold 5 / test 15.
  If fewer than 36 clusters carry C/C++ submissions, the pre-registered
  fallback applies: dev-gold 4, test 12 (gold then spans ≥10 of them).
* Only clusters with failing C/C++ rows are eligible for dev-gold and test.
  Assignment is seeded and stratified by failing-row count so test is not
  starved; the seed, inputs hash and every count are written to the report.

The split must exist before Eman mines wrong→Accepted pairs (train side only).

    python scripts/cluster_codestream_problems.py [--raw DIR] [--seed 20261021]

Outputs
  data/misconception_dataset/splits/codestream_clusters.csv
  data/misconception_dataset/reports/codestream_cluster_split.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
from collections import Counter, defaultdict

from codestream_common import DATASET_DIR, find_raw, load_problems, load_submissions

THRESHOLD = 0.8
FAILING = {"Wrong Answer", "Presentation Error", "Runtime Error", "Time Limit Exceeded",
           "Memory Limit Exceeded"}


def cluster_statements(ids: list[str], texts: list[str], threshold: float = THRESHOLD):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vec = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=1, sublinear_tf=True,
                          token_pattern=r"(?u)\b\w+\b")
    X = vec.fit_transform(texts)
    S = cosine_similarity(X)
    parent = list(range(len(ids)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    pairs = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if S[i, j] > threshold:
                pairs.append((ids[i], ids[j], float(S[i, j])))
                parent[find(i)] = find(j)
    comps = defaultdict(list)
    for i, pid in enumerate(ids):
        comps[find(i)].append(pid)
    # stable cluster ids: ordered by smallest problem id in the component
    ordered = sorted(comps.values(), key=lambda m: min(m))
    assign = {}
    for k, members in enumerate(ordered, 1):
        for pid in members:
            assign[pid] = f"cs-clu-{k:03d}"
    return assign, pairs


def assign_pools(cluster_fail: dict[str, int], cluster_cfam: dict[str, int], seed: int,
                 n_test: int, n_dev: int):
    """Seeded, stratified pool assignment. Returns (pool_by_cluster, notes)."""
    rng = random.Random(seed)
    eligible = [c for c, n in cluster_fail.items() if n > 0]
    usable = len([c for c, n in cluster_cfam.items() if n > 0])
    notes = []
    if usable < 36:
        n_test, n_dev = 12, 4
        notes.append(f"{usable} clusters carry C/C++ submissions (<36): pre-registered "
                     "fallback applied — dev-gold 4, test 12, gold spans >=10 test clusters.")
    if len(eligible) < n_test + n_dev + 1:
        raise SystemExit(f"only {len(eligible)} clusters with failing C/C++ rows; cannot split")
    # strata of 3 by failing-row count: each stratum sends ~ its share to each pool
    ranked = sorted(eligible, key=lambda c: (-cluster_fail[c], c))
    pool = {}
    quota = {"test": n_test, "dev_gold": n_dev}
    n_train_target = len(eligible) - n_test - n_dev
    quota["train"] = n_train_target
    total = len(eligible)
    for start in range(0, total, 3):
        block = ranked[start:start + 3]
        rng.shuffle(block)
        for c in block:
            remaining = {p: q for p, q in quota.items() if q > 0}
            # pick the pool furthest behind its proportional share
            done = start
            def lag(p):
                share = {"test": n_test, "dev_gold": n_dev, "train": n_train_target}[p] / total
                taken = sum(1 for v in pool.values() if v == p)
                return share * (done + 1) - taken
            choice = max(sorted(remaining), key=lambda p: (lag(p), rng.random()))
            pool[c] = choice
            quota[choice] -= 1
            done += 1
    for c in cluster_cfam:
        pool.setdefault(c, "train")  # clusters with no failing C/C++ rows: train side
    return pool, notes, n_test, n_dev


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=None)
    ap.add_argument("--seed", type=int, default=20261021)
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    a = ap.parse_args()
    raw = find_raw(a.raw)
    probs = load_problems(raw)
    subs = load_submissions(raw)
    ids = sorted(probs)
    texts = [probs[p].statement for p in ids]
    assign, pairs = cluster_statements(ids, texts, a.threshold)

    fail = Counter()
    cfam = Counter()
    accepted = Counter()
    users = defaultdict(set)
    for s in subs:
        c = assign.get(s.problem_id)
        if c is None:
            continue
        cfam[c] += 1
        users[c].add(s.user_id)
        if s.verdict in FAILING:
            fail[c] += 1
        if s.verdict == "Accepted":
            accepted[c] += 1
    clusters = sorted(set(assign.values()))
    for c in clusters:
        fail.setdefault(c, 0)
        cfam.setdefault(c, 0)
    pool, notes, n_test, n_dev = assign_pools(dict(fail), dict(cfam), a.seed, 15, 5)

    out_dir = DATASET_DIR / "splits"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "codestream_clusters.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["problem_id", "source_problem_id", "problem_cluster", "pool",
                    "cfamily_submissions", "failing_cfamily", "accepted_cfamily"])
        per_problem_f = Counter(s.problem_id for s in subs if s.verdict in FAILING)
        per_problem_a = Counter(s.problem_id for s in subs if s.verdict == "Accepted")
        per_problem_n = Counter(s.problem_id for s in subs)
        for pid in ids:
            c = assign[pid]
            w.writerow([pid, probs[pid].source_problem_id, c, pool[c], per_problem_n[pid],
                        per_problem_f[pid], per_problem_a[pid]])

    h = hashlib.sha256("\n".join(texts).encode()).hexdigest()[:16]
    pool_counts = Counter(pool.values())
    by_pool = defaultdict(lambda: Counter())
    pool_users = defaultdict(set)
    for c in clusters:
        by_pool[pool[c]]["clusters"] += 1
        by_pool[pool[c]]["failing"] += fail[c]
        by_pool[pool[c]]["accepted"] += accepted[c]
        by_pool[pool[c]]["cfamily"] += cfam[c]
        pool_users[pool[c]] |= users[c]
    lines = [
        "# CodeStream problem clusters and pool split",
        "",
        "Generated by `scripts/cluster_codestream_problems.py`. Do not edit by hand.",
        "",
        f"- Problems: {len(ids)} · clusters: {len(clusters)} · TF-IDF (1–2-gram) cosine > {a.threshold}",
        f"- Seed: `{a.seed}` · statements hash: `{h}`",
        f"- Clusters with C/C++ submissions: {sum(1 for c in clusters if cfam[c])}; "
        f"with failing C/C++ rows: {sum(1 for c in clusters if fail[c])}",
        f"- Pools: train {pool_counts['train']} · dev-gold {pool_counts['dev_gold']} · test {pool_counts['test']}"
        f" (targets: dev-gold {n_dev}, test {n_test})",
        "",
    ]
    for n in notes:
        lines.append(f"> {n}")
        lines.append("")
    lines += ["| Pool | Clusters | C/C++ subs | Failing C/C++ | Accepted C/C++ | Users |",
              "|---|---:|---:|---:|---:|---:|"]
    for p in ("train", "dev_gold", "test"):
        b = by_pool[p]
        lines.append(f"| {p} | {b['clusters']} | {b['cfamily']} | {b['failing']} | {b['accepted']} | {len(pool_users[p])} |")
    lines += ["", "## Merged pairs (cosine > threshold)", ""]
    if pairs:
        lines += ["| Problem A | Problem B | Cosine |", "|---|---|---:|"]
        lines += [f"| {x} | {y} | {s:.3f} |" for x, y, s in sorted(pairs)]
    else:
        lines.append("None — every problem is its own cluster.")
    lines += ["", "## Rules", "",
              "- No row from a test or dev-gold cluster — including mutants seeded from them — reaches training.",
              "- Reverse-mutation mining (Eman, E1) reads train-side clusters only.",
              "- Users overlapping train and test are expected (same course); the gold user-sensitivity check reports it.",
              "- Rayaan's `splits.csv` must respect this pool assignment (G7)."]
    rep = DATASET_DIR / "reports" / "codestream_cluster_split.md"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
