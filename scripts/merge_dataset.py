#!/usr/bin/env python3
"""Task 8 — the three-lane merge + G7 leakage gate (master plan §7, R5).

Pipeline (one entry point, `merge`):

    annotations/tier*.jsonl
        -> G1 validate every lane row (verify_dataset.check_row)
        -> join label_mapping.csv (family/modeled/hard3; pre-registered
           merged_into folds execute as a join, never a regeneration)
        -> resolve each row's own code from the raw corpus
        -> dedupe (token 5-gram Jaccard >= 0.8, keep-first by row_id)
        -> join cluster_assignments.csv -> problem_cluster + split
        -> G7 leakage checks
        -> annotations/labels.jsonl + features/features.csv
           + splits/splits.csv + reports/merge_report.json

Binding rulings encoded here (2026-10-23 three-lane merge):

- **Only `tier*.jsonl` are lane inputs.** A previous run's `labels.jsonl`
  sits in the same directory and must never be re-merged.
- **Duplicate row_ids across lanes fail loudly** — two lanes claiming one
  row is an integration bug, not something to overwrite.
- **G1 runs before anything is written**: an invalid lane row aborts the
  merge with no partial outputs.
- **SYNTHETIC rows have no own code.** Their `source_record_id` is the
  *seed* submission, shared by many mutants; MinHash on seed code would
  collapse distinct mutants of one seed. They therefore dedupe by
  identity `(seed_ref, mutation_op, problem_id, label)` — the correct
  notion of a duplicate mutant. Code-bearing rows (CODESTREAM,
  PROGPEDIA) dedupe by token 5-gram Jaccard >= 0.8 over their own code.
  The plan names MinHash for scale; at pilot scale exact pairwise
  Jaccard is affordable and strictly stricter (no candidate misses) with
  identical threshold semantics — revisit LSH banding at >= 1e5 rows.
- **Rows inherit their problem's cluster split** (§13.4); a labeled row
  whose problem has no cluster row fails (G7 integrity), never guessed.
- **Structural violations raise** (duplicate row_id, G1 issues, missing
  cluster, cluster table straddling splits). **Structural leakage
  findings** (clusters/seed groups straddling splits, cross-split code
  twins) exit the CLI non-zero; **PSI drift is reported loudly** — the
  plan's PSI<0.2 gate is specced for train/val (same pool) and runs at
  training time (T9), while the merge's train-vs-test probe exists to
  surface pool asymmetry. Artifacts are written for inspection, never
  silently repaired.

Usage:
    python scripts/merge_dataset.py \
        [--dataset-dir data/misconception_dataset] \
        [--index-csv .../normalized/submissions/submissions.csv] \
        [--raw-root G:/TraceLearn/Datasets_RAW]
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_dataset import check_row, load_jsonl, load_proof_keys  # noqa: E402
from tracelearn_features.normalize import normalize_row  # noqa: E402
from tracelearn_features.schema import FEATURE_BLOCKS, feature_names  # noqa: E402

DEFAULT_DATASET_DIR = ROOT / "data" / "misconception_dataset"
DEFAULT_INDEX_CSV = (
    ROOT / "data" / "Data_from_Datasets" / "intermediate" / "normalized"
    / "submissions" / "submissions.csv"
)
DEFAULT_RAW_ROOT = Path("G:/TraceLearn/Datasets_RAW")

JACCARD_THRESHOLD = 0.8
PSI_THRESHOLD = 0.2
PSI_MIN_VALUES = 10          # per side before a PSI number means anything


# ----------------------------------------------------------------- loading


def load_index(index_csv: Path) -> dict[str, str]:
    """normalized submissions index: source_record_id -> source_code_path."""
    index: dict[str, str] = {}
    with Path(index_csv).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or "source_record_id" not in reader.fieldnames:
            raise ValueError(f"{index_csv}: no source_record_id column (join column empty)")
        for rec in reader:
            srs = (rec.get("source_record_id") or "").strip()
            if srs:
                index[srs] = (rec.get("source_code_path") or "").strip()
    return index


def load_cluster_table(path: Path) -> dict[str, tuple[str, str]]:
    """cluster_assignments.csv: problem_id -> (cluster_id, split).

    Fails if one cluster_id is assigned two different splits — honoring
    both would be impossible and silently picking one leaks a split.
    """
    table: dict[str, tuple[str, str]] = {}
    cluster_splits: dict[str, set[str]] = defaultdict(set)
    with Path(path).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"problem_id", "cluster_id", "split"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path}: missing columns {sorted(required)}")
        for rec in reader:
            pid, cid, split = rec["problem_id"], rec["cluster_id"], rec["split"]
            if pid in table and table[pid] != (cid, split):
                raise ValueError(f"{path}: problem {pid!r} has conflicting cluster rows")
            table[pid] = (cid, split)
            cluster_splits[cid].add(split)
    straddlers = {cid: sorted(s) for cid, s in cluster_splits.items() if len(s) > 1}
    if straddlers:
        raise ValueError(
            f"{path}: cluster straddles splits (leakage) {straddlers} — never silently re-split"
        )
    return table


def load_label_registry(path: Path) -> dict[str, dict[str, str]]:
    """label_mapping.csv keyed by label (kind=label rows only)."""
    registry: dict[str, dict[str, str]] = {}
    with Path(path).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for rec in reader:
            if (rec.get("kind") or "").strip() != "label":
                continue
            label = (rec.get("label") or "").strip()
            if label:
                registry[label] = rec
    return registry


# ------------------------------------------------------- review decisions


def apply_review_decisions(
    rows: list[dict[str, Any]], path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply signed-off pre-review decisions (``annotations/label_review_decisions.jsonl``).

    confirm + human basis  -> label_source 'human', confidence 1.0;
    confirm + spot-check   -> unchanged (its LF audit already moved the confidence);
    relabel (human only)   -> new label, label_source 'human', confidence 1.0;
    reject                 -> row dropped (counted in the merge report).
    Decisions for unknown row ids are reported, never silently ignored.
    """
    stats: dict[str, Any] = {"file": path.name, "applied": Counter(), "unknown_row_ids": []}
    if not path.is_file():
        stats["file"] = None
        return rows, stats
    decisions: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                d = json.loads(line)
                decisions[d["row_id"]] = d
    by_id = {r.get("row_id"): r for r in rows}
    stats["unknown_row_ids"] = sorted(rid for rid in decisions if rid not in by_id)
    kept = []
    for row in rows:
        d = decisions.get(row.get("row_id"))
        if d is None:
            kept.append(row)
            continue
        action, basis = d.get("action"), d.get("basis")
        if action == "reject":
            stats["applied"]["reject"] += 1
            continue
        row = dict(row)
        if action == "relabel":
            if basis != "human":
                raise ValueError(f"review decision for {row['row_id']}: only a human may relabel")
            row["secondary_labels"] = sorted(set(row.get("secondary_labels") or []) | {row["label"]})
            row["label"] = d["label"]
        if basis == "human":
            row["label_source"] = "human"
            row["label_confidence"] = 1.0
        row["review"] = {k: d.get(k) for k in ("action", "basis", "item_id", "signed_off_by")}
        stats["applied"][f"{action}:{basis}"] += 1
        kept.append(row)
    stats["applied"] = dict(stats["applied"])
    return kept, stats


# ------------------------------------------------------------ code resolution


def resolve_code(
    row: dict[str, Any],
    raw_root: Path,
    ref_index: dict[tuple[str, str], str] | None = None,
) -> str | None:
    """A row's OWN code, or None when it has none.

    - SYNTHETIC rows: None by construction — `source_record_id` is the
      seed submission, shared by many mutants; seed code is not the
      mutant's code.
    - `path#record_id` refs (CodeStream CSV): the record's source_code.
    - plain relative paths (PROGPedia .c files): the file's text.
    Unreadable paths return None — kept and reported, never guessed.
    """
    if row.get("dataset_source") == "SYNTHETIC":
        return None
    source_path = row.get("source_code_path")
    if not isinstance(source_path, str) or not source_path:
        return None
    if "#" in source_path:
        rel, record_id = source_path.split("#", 1)
        if ref_index is not None:
            return ref_index.get((rel, record_id))
        path = Path(raw_root) / rel
        if not path.is_file():
            return None
        with path.open(newline="", encoding="utf-8", errors="replace") as fh:
            for rec in csv.DictReader(fh):
                if rec.get("submission_id") == record_id:
                    return rec.get("source_code")
        return None
    path = Path(raw_root) / source_path
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def prefetch_csv_refs(
    rows: Iterable[dict[str, Any]],
    index: dict[str, str],
    raw_root: Path,
) -> dict[tuple[str, str], str]:
    """One streaming pass per `path#record_id` source, keeping only the
    referenced records (bounded memory even for multi-GB CSVs)."""
    wanted: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        source_path = index.get(row.get("source_record_id") or "") or row.get("source_code_path")
        if isinstance(source_path, str) and "#" in source_path:
            rel, record_id = source_path.split("#", 1)
            wanted[rel].add(record_id)
    ref_index: dict[tuple[str, str], str] = {}
    for rel, ids in wanted.items():
        path = Path(raw_root) / rel
        if not path.is_file():
            continue  # rows resolve to None -> counted as code_uncovered
        with path.open(newline="", encoding="utf-8", errors="replace") as fh:
            for rec in csv.DictReader(fh):
                record_id = rec.get("submission_id")
                if record_id in ids:
                    ref_index[(rel, record_id)] = rec.get("source_code") or ""
                    ids.discard(record_id)
                    if not ids:
                        break
    return ref_index


# ------------------------------------------------------------------ dedupe


def token_shingles(code: str, n: int = 5) -> set[tuple[str, ...]]:
    """Token n-grams: identifiers/numbers/operators/ punctuation, windows
    of `n` consecutive tokens (shorter code falls back to one window)."""
    import re

    tokens = re.findall(r"[A-Za-z_]\w+|\d+|==|!=|<=|>=|&&|\|\||[^\s]", code)
    if not tokens:
        return set()
    if len(tokens) < n:
        return {tuple(tokens)}
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def jaccard(a: set[Any], b: set[Any]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def dedupe_rows(
    rows: Sequence[dict[str, Any]],
    code_by_rid: dict[str, str | None],
    threshold: float = JACCARD_THRESHOLD,
) -> tuple[list[dict[str, Any]], int, list[dict[str, str]]]:
    """Drop duplicates, keep-first by row_id. Returns (kept, n_deduped, conflicts).

    Two bases, never mixed:
    - code-bearing rows: own-code token 5-gram Jaccard >= `threshold`;
    - SYNTHETIC rows: exact identity (seed_ref, mutation_op, problem_id,
      label) — seed code must not drive mutant dedupe.

    `conflicts` records dropped twins whose labels disagree — surfaced in
    the report, never silently resolved.
    """
    kept: list[dict[str, Any]] = []
    kept_code: list[tuple[str, set[tuple[str, ...]], str]] = []
    kept_identities: set[tuple[Any, ...]] = set()
    dropped = 0
    conflicts: list[dict[str, str]] = []

    for row in sorted(rows, key=lambda r: str(r.get("row_id"))):
        rid = str(row.get("row_id"))
        code = code_by_rid.get(rid)
        if code is None:
            identity = (
                row.get("seed_ref") or row.get("source_record_id"),
                row.get("mutation_op"),
                row.get("problem_id"),
                row.get("label"),
            )
            if identity in kept_identities:
                dropped += 1
                continue
            kept_identities.add(identity)
        else:
            shingles = token_shingles(code)
            twin = next(
                (k for k, prev, _ in kept_code if jaccard(shingles, prev) >= threshold),
                None,
            )
            if twin is not None:
                dropped += 1
                keeper = next(r for r in kept if r.get("row_id") == twin)
                if keeper.get("label") != row.get("label"):
                    conflicts.append(
                        {"kept": twin, "dropped": rid,
                         "kept_label": str(keeper.get("label")),
                         "dropped_label": str(row.get("label"))}
                    )
                continue
            kept_code.append((rid, shingles, str(row.get("label"))))
        kept.append(row)
    return kept, dropped, conflicts


# ---------------------------------------------------------------- PSI


def psi(base: Sequence[Any], comp: Sequence[Any]) -> float:
    """Population Stability Index over decile bins of the pooled sample.

    0 == identical distributions; the conventional drift alarm is 0.2.
    Missing values are excluded; <1 comparable value on either side is
    0.0 (no evidence of drift, not evidence of none).
    """
    def clean(xs: Sequence[Any]) -> list[float]:
        out = []
        for x in xs:
            if x is None:
                continue
            try:
                v = float(x)
            except (TypeError, ValueError):
                continue
            if not math.isnan(v):
                out.append(v)
        return out

    a, b = clean(base), clean(comp)
    if not a or not b:
        return 0.0
    pool = sorted(a + b)
    k = 10
    edges = sorted(
        {pool[min(len(pool) - 1, int(round(i * (len(pool) - 1) / k)))] for i in range(k + 1)}
    )
    if len(edges) < 2:
        return 0.0

    def dist(xs: list[float]) -> list[float]:
        counts = [0] * (len(edges) - 1)
        for v in xs:
            # rightmost edge is inclusive (a value equal to the pooled max
            # belongs to the last bin, not past it)
            idx = min(len(counts) - 1, bisect.bisect_right(edges, v) - 1)
            counts[max(0, idx)] += 1
        n = len(xs)
        return [c / n for c in counts]

    p, q = dist(a), dist(b)
    eps = 1e-6
    return sum((pi - qi) * math.log((pi + eps) / (qi + eps)) for pi, qi in zip(p, q))


# ---------------------------------------------------------------- G7


def g7_checks(
    labels: Sequence[dict[str, Any]],
    clusters: dict[str, tuple[str, str]],
    code_by_rid: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """G7 leakage checks (§9.0): clusters never straddle splits, seed
    groups stay intact, cross-split code twins = 0.

    `clusters` maps problem_id -> (cluster_id, split); a problem missing
    there counts as "<unassigned>" so it surfaces as a conflict rather
    than crashing the gate.
    """

    def split_of(row: dict[str, Any]) -> str:
        entry = clusters.get(row.get("problem_id") or "")
        return entry[1] if entry else "<unassigned>"

    # 1) cluster -> split integrity (table + rows agree)
    cluster_splits: dict[str, set[str]] = defaultdict(set)
    for pid, (cid, split) in clusters.items():
        cluster_splits[cid].add(split)
    n_conflicts = sum(1 for splits in cluster_splits.values() if len(splits) > 1)
    for row in labels:
        entry = clusters.get(row.get("problem_id") or "")
        if entry is None:
            n_conflicts += 1
        elif row.get("problem_cluster") is not None and row["problem_cluster"] != entry[0]:
            n_conflicts += 1

    # 2) seed groups: rows linked by sharing a seed_ref, or by one row's
    #    source_record_id being another row's seed_ref (the seed's own row)
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    by_seed: dict[str, int] = {}
    for i, row in enumerate(labels):
        find(i)
        for key in (row.get("seed_ref"), row.get("source_record_id")):
            if isinstance(key, str) and key:
                if key in by_seed:
                    union(i, by_seed[key])
                else:
                    by_seed[key] = i
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(labels)):
        groups[find(i)].append(i)
    seed_conflicts: list[dict[str, Any]] = []
    for members in groups.values():
        splits = {split_of(labels[i]) for i in members}
        if len(splits) > 1:
            seed_conflicts.append(
                {
                    "seed": labels[members[0]].get("seed_ref") or labels[members[0]].get("source_record_id"),
                    "row_ids": sorted(str(labels[i].get("row_id")) for i in members),
                    "splits": sorted(splits),
                }
            )

    # 3) cross-split code twins >= 0.8 (independent recomputation — this
    #    re-checks dedupe rather than trusting it)
    twins = 0
    twin_examples: list[dict[str, str]] = []
    if code_by_rid is not None:
        code_rows = [
            (str(r.get("row_id")), split_of(r), token_shingles(code_by_rid[str(r.get("row_id"))]))
            for r in labels
            if code_by_rid.get(str(r.get("row_id")))
        ]
        for i in range(len(code_rows)):
            for j in range(i + 1, len(code_rows)):
                if code_rows[i][1] != code_rows[j][1] and jaccard(code_rows[i][2], code_rows[j][2]) >= JACCARD_THRESHOLD:
                    twins += 1
                    if len(twin_examples) < 5:
                        twin_examples.append({"kept": code_rows[i][0], "twin": code_rows[j][0]})

    return {
        "cluster_split_conflicts": n_conflicts,
        "seed_group_conflicts": len(seed_conflicts),
        "seed_groups": {"ok": not seed_conflicts, "conflicts": seed_conflicts},
        "cross_split_twins": twins,
        "twin_examples": twin_examples,
        "twins_checked": code_by_rid is not None,
    }


# ------------------------------------------------------------- features


def flatten_features(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Registry-order flat records: row_id, label, then every canonical
    feature. Missing block entries -> NaN (a lane block that was never
    mined stays null, §6/§9.0); bools -> 0/1."""
    names = feature_names()
    flat: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: str(r.get("row_id"))):
        rec: dict[str, Any] = {"row_id": row.get("row_id"), "label": row.get("label")}
        for name in names:
            block, short = name.split(".", 1)
            source = row.get(block)
            value = source.get(short) if isinstance(source, dict) else None
            if value is None:
                value = float("nan")
            elif isinstance(value, bool):
                value = int(value)
            rec[name] = value
        flat.append(rec)
    return flat


# ---------------------------------------------------------------- merge


def merge(
    dataset_dir: Path,
    index_csv: Path,
    raw_root: Path,
    threshold: float = JACCARD_THRESHOLD,
) -> dict[str, Any]:
    """Run the full merge; returns the merge report (also written to
    reports/merge_report.json). Structural problems raise ValueError
    before any output is written."""
    ds = Path(dataset_dir)

    # 1) lane inputs: tier*.jsonl only (labels.jsonl of a past run excluded)
    tier_files = sorted((ds / "annotations").glob("tier*.jsonl"))
    if not tier_files:
        raise ValueError(f"no tier*.jsonl lane inputs under {ds / 'annotations'}")
    rows: list[dict[str, Any]] = []
    parse_issues: list[Any] = []
    for path in tier_files:
        loaded, issues = load_jsonl(path)
        rows.extend(loaded)
        parse_issues.extend(issues)
    if parse_issues:
        raise ValueError(f"malformed JSONL: {[i.detail for i in parse_issues[:3]]}")

    # 2) duplicate row_ids across lanes
    dups = sorted(rid for rid, n in Counter(r.get("row_id") for r in rows).items() if n > 1)
    if dups:
        raise ValueError(f"duplicate row_id across lanes: {dups[:5]}")

    # 2b) signed-off review decisions (confirm / relabel / reject)
    rows, review_stats = apply_review_decisions(
        rows, ds / "annotations" / "label_review_decisions.jsonl"
    )

    # 3) G1 on every lane row — invalid lanes abort before any output
    index = load_index(index_csv)
    proof_keys = load_proof_keys(ds / "annotations" / "mutant_proofs")
    g1_issues = []
    for row in rows:
        g1_issues.extend(check_row(row, set(index), proof_keys=proof_keys))
    if g1_issues:
        detail = "; ".join(f"{i.row_id}:{i.check}" for i in g1_issues[:5])
        raise ValueError(f"G1 validation failed ({len(g1_issues)} issue(s)): {detail}")

    # 4) label registry join: family/modeled/hard3 + pre-registered merges
    registry = load_label_registry(ds / "label_mapping.csv")
    n_merged = 0
    for row in rows:
        label = row["label"]
        entry = registry.get(label)
        if entry is not None and (entry.get("merged_into") or "").strip():
            label = entry["merged_into"].strip()
            row["label"] = label
            n_merged += 1
            entry = registry.get(label)
        if entry is None:
            raise ValueError(f"label_mapping has no row for label {label!r} (row {row.get('row_id')})")
        row["family"] = entry.get("family") or None
        row["modeled"] = (entry.get("modeled") or "").strip().lower() == "yes"
        row["hard3"] = (entry.get("hard3") or "").strip().lower() == "yes"

    # 5) own-code resolution (one pass per CSV source; plain files as needed)
    ref_index = prefetch_csv_refs(rows, index, raw_root)
    code_by_rid: dict[str, str | None] = {}
    n_uncovered = 0
    for row in rows:
        rid = str(row["row_id"])
        source_path = index.get(row.get("source_record_id") or "") or row.get("source_code_path")
        resolved_row = dict(row)
        resolved_row["source_code_path"] = source_path
        code = resolve_code(resolved_row, raw_root, ref_index=ref_index)
        code_by_rid[rid] = code
        if row["dataset_source"] != "SYNTHETIC" and code is None:
            n_uncovered += 1

    # 6) dedupe (kept, dropped, label conflicts)
    before = len(rows)
    rows, n_deduped, dedupe_conflicts = dedupe_rows(rows, code_by_rid, threshold=threshold)

    # 6b) normalize each lane's raw evidence onto the canonical registry.
    # tier0 embeds the mutant's source; CodeStream's own code was resolved in
    # step 5; PROGPedia already arrives canonical. Without this step
    # flatten_features() would emit NaN for evidence the lane actually
    # supplied in its own vocabulary (T9 root cause: tier0 exposed only
    # static.loc, tier1a only 3 canonical columns).
    rows = [
        normalize_row(row, code=code_by_rid.get(str(row["row_id"])))
        for row in rows
    ]

    # 7) cluster/split join — an unlabeled-cluster problem is an integrity
    #    failure, never guessed
    clusters = load_cluster_table(ds / "splits" / "cluster_assignments.csv")
    missing = sorted({str(r["problem_id"]) for r in rows if r["problem_id"] not in clusters})
    if missing:
        raise ValueError(
            f"{len(missing)} labeled problem(s) have no cluster row (G7 integrity): {missing[:5]}"
        )
    for row in rows:
        cluster_id, _split = clusters[row["problem_id"]]
        row["problem_cluster"] = cluster_id

    # 8) G7 leakage checks — reported, never silently repaired
    kept_rids = {str(r["row_id"]) for r in rows}
    kept_code = {k: v for k, v in code_by_rid.items() if k in kept_rids}
    g7 = g7_checks(rows, clusters, code_by_rid=kept_code)

    # 9) PSI train vs test on shared numeric features
    # numeric features by CANONICAL name (block.short) — keying by short
    # name silently matches nothing in the flat records
    numeric = {
        f"{block_name}.{short}"
        for block_name, block in FEATURE_BLOCKS.items()
        for short, ftype in block.items()
        if ftype in ("int", "float")
    }
    flat = flatten_features(rows)
    split_of_row = {str(r["row_id"]): clusters[r["problem_id"]][1] for r in rows}
    by_side: dict[str, dict[str, list[Any]]] = {"train": defaultdict(list), "test": defaultdict(list)}
    for rec in flat:
        side = split_of_row.get(str(rec["row_id"]))
        if side in by_side:
            for name in numeric:
                by_side[side][name].append(rec.get(name))
    psi_values: list[tuple[str, float]] = []
    for name in sorted(numeric):
        a, b = by_side["train"][name], by_side["test"][name]
        if sum(1 for v in a if v is not None and not (isinstance(v, float) and math.isnan(v))) < PSI_MIN_VALUES:
            continue
        if sum(1 for v in b if v is not None and not (isinstance(v, float) and math.isnan(v))) < PSI_MIN_VALUES:
            continue
        psi_values.append((name, psi(a, b)))
    psi_worst = max(psi_values, key=lambda kv: kv[1]) if psi_values else None
    psi_report = {
        "comparison": "train_vs_test",
        "gate_scope": (
            "plan G7's PSI<0.2 gate is specced for train/val (same pool) and is "
            "evaluated at training time (T9); this train-vs-test probe is informational "
            "— violations here reflect pool asymmetry (frozen CodeStream-only test) and "
            "require team review before G3, not a merge abort"
        ),
        "threshold": PSI_THRESHOLD,
        "n_features_checked": len(psi_values),
        "max": round(psi_worst[1], 4) if psi_worst else None,
        "worst_feature": psi_worst[0] if psi_worst else None,
        "violations": [
            {"feature": n, "psi": round(v, 4)} for n, v in sorted(psi_values, key=lambda kv: -kv[1])
            if v >= PSI_THRESHOLD
        ],
    }

    # 10) outputs
    per_source = dict(Counter(str(r["dataset_source"]) for r in rows))
    per_split = dict(Counter(clusters[r["problem_id"]][1] for r in rows))

    # per-block row availability per source: lane gaps (a null static
    # block, an empty warnings dict) are a cross-lane integration fact the
    # report must surface, not something to paper over
    def block_present(row: dict[str, Any], block: str) -> bool:
        source = row.get(block)
        if not isinstance(source, dict):
            return False
        for name, value in source.items():
            if name == "available":
                # `available` is a measurement flag, not evidence. A lane
                # that says available=False supplied no values for the block.
                continue
            if value is None:
                continue
            if isinstance(value, float) and math.isnan(value):
                continue
            return True
        return False

    feature_availability: dict[str, dict[str, float]] = {}
    for block in FEATURE_BLOCKS:
        per_source_seen: dict[str, list[bool]] = defaultdict(list)
        for row in rows:
            per_source_seen[str(row["dataset_source"])].append(block_present(row, block))
        feature_availability[block] = {
            source: round(sum(flags) / len(flags), 3)
            for source, flags in sorted(per_source_seen.items())
        }

    report: dict[str, Any] = {
        "inputs": [p.name for p in tier_files],
        "review_decisions": review_stats,
        "n_rows_before_dedupe": before,
        "n_rows": len(rows),
        "deduped": n_deduped,
        "dedupe_threshold": threshold,
        "dedupe_label_conflicts": dedupe_conflicts,
        "merged_labels": n_merged,
        "code_uncovered": n_uncovered,
        "per_source": per_source,
        "per_split": per_split,
        "feature_availability": feature_availability,
        "g1": {"ok": True, "n_rows": before},
        "g7": g7,
        "psi": psi_report,
    }

    ann_dir = ds / "annotations"
    features_dir = ds / "features"
    splits_dir = ds / "splits"
    reports_dir = ds / "reports"
    for d in (features_dir, reports_dir):
        d.mkdir(parents=True, exist_ok=True)

    with (ann_dir / "labels.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for row in sorted(rows, key=lambda r: str(r["row_id"])):
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    names = feature_names()
    with (features_dir / "features.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["row_id", "label"] + names, lineterminator="\n")
        writer.writeheader()
        for rec in flat:
            writer.writerow(rec)

    with (splits_dir / "splits.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["row_id", "problem_id", "cluster_id", "split"])
        for row in sorted(rows, key=lambda r: str(r["row_id"])):
            cluster_id, split = clusters[row["problem_id"]]
            writer.writerow([row["row_id"], row["problem_id"], cluster_id, split])

    with (reports_dir / "merge_report.json").open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    return report


def g7_all_ok(report: dict[str, Any]) -> bool:
    """Structural G7 verdict: clusters/seed-groups never straddle splits,
    cross-split code twins = 0. PSI is reported (see gate_scope) but its
    plan-specified train/val gate runs at training time."""
    g7 = report["g7"]
    return (
        g7["cluster_split_conflicts"] == 0
        and g7["seed_group_conflicts"] == 0
        and g7["cross_split_twins"] == 0
    )


# ------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--index-csv", type=Path, default=DEFAULT_INDEX_CSV)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--threshold", type=float, default=JACCARD_THRESHOLD)
    args = parser.parse_args(argv)

    try:
        report = merge(
            dataset_dir=args.dataset_dir,
            index_csv=args.index_csv,
            raw_root=args.raw_root,
            threshold=args.threshold,
        )
    except ValueError as exc:
        print(f"FAIL  merge aborted: {exc}")
        return 1

    print(f"inputs:    {', '.join(report['inputs'])}")
    print(f"rows:      {report['n_rows_before_dedupe']} before dedupe -> {report['n_rows']} kept "
          f"({report['deduped']} dropped @ Jaccard>={report['dedupe_threshold']})")
    print(f"per source: {report['per_source']}")
    print(f"per split:  {report['per_split']}")
    print(f"merged labels: {report['merged_labels']}  code uncovered: {report['code_uncovered']}")
    if report["dedupe_label_conflicts"]:
        print(f"NOTE  {len(report['dedupe_label_conflicts'])} dropped twin(s) disagreed on label — "
              f"see merge_report.json")
    g7 = report["g7"]
    print(f"G7: clusters_straddling_splits={g7['cluster_split_conflicts']} "
          f"seed_groups_straddling_splits={g7['seed_group_conflicts']} "
          f"cross_split_twins={g7['cross_split_twins']}")
    psi_ = report["psi"]
    print(f"PSI train-vs-test (informational pool probe): checked={psi_['n_features_checked']} "
          f"max={psi_['max']} ({psi_['worst_feature']})")
    for v in psi_["violations"]:
        print(f"NOTE  PSI drift {v['feature']}={v['psi']} >= {psi_['threshold']} — pool asymmetry "
              f"(frozen CodeStream-only test vs mixed train); plan's train/val gate runs at T9")
    for block, avail in report["feature_availability"].items():
        gaps = {s: f for s, f in avail.items() if f < 1.0}
        if gaps:
            print(f"NOTE  feature block {block!r} absent on some rows: {gaps}")
    if not g7_all_ok(report):
        print("FAIL  G7 leakage gate red — artifacts written, see reports/merge_report.json")
        return 1
    print("MERGE PASS — labels.jsonl, features.csv, splits.csv, merge_report.json written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
