#!/usr/bin/env python3
"""G1 resolvers + Layer-2 per-class report (master plan §9.0 G1, §8, R2).

R2 milestone runner. Two responsibilities:

1. **G1 resolvers** (`verify`, `check_row`) — hard gate, exit 1 on any issue:
   - labels <-> normalized join: every row's `source_record_id` resolves in the
     normalized submissions index (0 orphans) — the traceability chain
     row_id -> lane JSONL -> raw file (§424);
   - enums clean: `label`, `label_source`, `dataset_source`, `language`,
     `taxonomy_version` all from their frozen vocabularies; `row_id` prefix
     matches `dataset_source` (mut-/cs-/pg-, §5);
   - `schema_version` present (non-null) on every row;
   - `label_confidence` present and within [0, 1]; `secondary_labels` a list.

2. **Layer-2 weekly gate** (`per_class_report`, `--per-class-report`) —
   prints class x lane x (certain/silver). Certain = execution-verified
   synthetic + `repair_verified` + `human` (Layer 4); silver = weak-rule (and
   synthetic rows never execution-verified). A class below its §8 certain floor
   is flagged `UNDER` (informational at R2 — the weekly fix-it process is a
   human gate, not a hard CI failure).

Read-only except stdout. Exit 0 only when every G1 check passes.

Usage:
    python scripts/verify_dataset.py \
        --dataset-dir data/misconception_dataset \
        [--normalized-ids ids.txt | --normalized-csv submissions.csv] \
        [--per-class-report]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DATASET_DIR = ROOT / "data" / "misconception_dataset"
DEFAULT_NORMALIZED_CSV = (
    ROOT / "data" / "Data_from_Datasets" / "intermediate" / "normalized"
    / "submissions" / "submissions.csv"
)

from tracelearn_features.taxonomy import (  # noqa: E402  (after sys.path bootstrap)
    LABEL_SOURCES,
    MODELED_LABELS,
    NO_MISCONCEPTION,
    TAXONOMY_VERSION,
)

# §5 row-ID prefixes per dataset_source.
ROW_ID_PREFIX = {
    "SYNTHETIC": "mut-",
    "CODESTREAM": "cs-",
    "PROGPEDIA": "pg-",
}

# §2.1: CodeNet is excluded from labels, so it is not a legal label source.
DATASET_SOURCES = frozenset(ROW_ID_PREFIX)

LABEL_VOCAB = frozenset(MODELED_LABELS) | {NO_MISCONCEPTION}
LANGUAGES = frozenset({"c", "cpp"})

# §8 "Certain floor (>=)" column — Layer-1 single source of truth.
CERTAIN_FLOOR: dict[str, int] = {
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

# Keys that must be present and non-null on every row (G1 "resolvers").
REQUIRED_KEYS = (
    "row_id",
    "dataset_source",
    "source_record_id",
    "problem_id",
    "language",
    "label",
    "label_source",
    "taxonomy_version",
    "schema_version",
)


@dataclass(frozen=True)
class RowIssue:
    check: str
    row_id: str
    detail: str


@dataclass
class Report:
    n_rows: int = 0
    issues: list[RowIssue] = field(default_factory=list)


def _row_id(row: dict[str, Any]) -> str:
    rid = row.get("row_id")
    return rid if isinstance(rid, str) else "<missing-row_id>"


def check_row(
    row: dict[str, Any],
    normalized_ids: set[str],
    proof_keys: set[tuple[str, str, str]] | None = None,
) -> list[RowIssue]:
    """Validate one dataset row against the G1 resolver rules."""
    issues: list[RowIssue] = []
    rid = _row_id(row)

    def add(check: str, detail: str) -> None:
        issues.append(RowIssue(check=check, row_id=rid, detail=detail))

    # --- required keys present and non-null -------------------------------
    for key in REQUIRED_KEYS:
        value = row.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            add(f"required:{key}", f"{key} missing or null")

    # --- enums clean -------------------------------------------------------
    label = row.get("label")
    if isinstance(label, str) and label and label not in LABEL_VOCAB:
        add("enum:label", f"label {label!r} not in taxonomy {TAXONOMY_VERSION}")

    label_source = row.get("label_source")
    if isinstance(label_source, str) and label_source and label_source not in LABEL_SOURCES:
        add("enum:label_source", f"label_source {label_source!r} not in {LABEL_SOURCES}")

    dataset_source = row.get("dataset_source")
    if isinstance(dataset_source, str) and dataset_source and dataset_source not in DATASET_SOURCES:
        add("enum:dataset_source", f"dataset_source {dataset_source!r} not in {sorted(DATASET_SOURCES)}")

    language = row.get("language")
    if isinstance(language, str) and language and language not in LANGUAGES:
        add("enum:language", f"language {language!r} not in {sorted(LANGUAGES)}")

    taxonomy_version = row.get("taxonomy_version")
    if isinstance(taxonomy_version, str) and taxonomy_version and taxonomy_version != TAXONOMY_VERSION:
        add("enum:taxonomy_version", f"taxonomy_version {taxonomy_version!r} != {TAXONOMY_VERSION!r}")

    # --- row_id prefix matches dataset_source (§5) -------------------------
    row_id = row.get("row_id")
    if isinstance(row_id, str) and isinstance(dataset_source, str) and dataset_source in ROW_ID_PREFIX:
        expected = ROW_ID_PREFIX[dataset_source]
        if not row_id.startswith(expected):
            add("row_id_prefix", f"row_id {row_id!r} does not start with {expected!r} for {dataset_source}")

    # --- label_confidence in [0, 1] and present (§3.5) ---------------------
    conf = row.get("label_confidence")
    if conf is None:
        add("label_confidence", "label_confidence missing or null")
    elif not isinstance(conf, (int, float)) or isinstance(conf, bool):
        add("label_confidence", f"label_confidence {conf!r} not numeric")
    elif not (0.0 <= float(conf) <= 1.0):
        add("label_confidence", f"label_confidence {conf} outside [0, 1]")

    # --- secondary_labels must be a list ----------------------------------
    secondary = row.get("secondary_labels")
    if secondary is not None and not isinstance(secondary, list):
        add("secondary_labels", f"secondary_labels {secondary!r} not a list")

    # --- labels <-> normalized join: 0 orphans ----------------------------
    # Ruling (three-lane merge 2026-10-23): template-derived SYNTHETIC mutants
    # have no real submission to point at; their provenance is the committed
    # mutant-proof corpus. A SYNTHETIC orphan is excused iff a proof matches
    # (problem_id, mutation_op, label) — evidence-based, never blanket; all
    # other sources keep the strict normalized join.
    source_record_id = row.get("source_record_id")
    if isinstance(source_record_id, str) and source_record_id and (
        normalized_ids or proof_keys is not None
    ):
        if source_record_id not in normalized_ids:
            proof_key = (row.get("problem_id"), row.get("mutation_op"), row.get("label"))
            excused = (
                row.get("dataset_source") == "SYNTHETIC"
                and proof_keys is not None
                and proof_key in proof_keys
            )
            if not excused:
                add("join:orphan", f"source_record_id {source_record_id!r} not in normalized index")

    return issues


def verify(
    rows: Iterable[dict[str, Any]],
    normalized_ids: set[str],
    proof_keys: set[tuple[str, str, str]] | None = None,
) -> Report:
    """Run G1 resolver checks across every row."""
    report = Report()
    for row in rows:
        report.n_rows += 1
        report.issues.extend(check_row(row, normalized_ids, proof_keys=proof_keys))
    return report


def load_proof_keys(proofs_dir: Path) -> set[tuple[str, str, str]]:
    """(problem_id, operator, label) triples from the mutant-proof corpus.

    Each proof json records the execution evidence behind a synthetic mutant;
    the triple links a template-derived row (source_record_id `tpl-*`) back to
    that evidence. Malformed proofs are skipped, never guessed.
    """
    keys: set[tuple[str, str, str]] = set()
    if not proofs_dir.is_dir():
        return keys
    for path in sorted(proofs_dir.glob("*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(obj, dict):
            continue
        triple = (obj.get("problem_id"), obj.get("operator"), obj.get("label"))
        if all(isinstance(x, str) and x for x in triple):
            keys.add(triple)
    return keys


# ------------------------------------------------------- Layer-2 report


def _is_certain(row: dict[str, Any]) -> bool:
    """Layer-4 certain-floor rule: execution-verified synthetic, repair_verified, human."""
    label_source = row.get("label_source")
    if label_source in ("human", "repair_verified"):
        return True
    if label_source == "synthetic":
        return row.get("verified_by_execution") is True
    return False  # weak_rule, or synthetic never execution-verified -> silver


def per_class_report(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """class -> {certain, silver, floor, under_floor, by_lane: {source: {certain, silver}}}."""
    stats: dict[str, dict[str, Any]] = {}

    def entry(label: str) -> dict[str, Any]:
        if label not in stats:
            stats[label] = {
                "certain": 0,
                "silver": 0,
                "floor": CERTAIN_FLOOR.get(label, 0),
                "by_lane": {},
            }
        return stats[label]

    for label in CERTAIN_FLOOR:  # seed every modeled label, even at zero
        entry(label)

    for row in rows:
        label = row.get("label")
        if not isinstance(label, str) or label not in CERTAIN_FLOOR:
            continue  # NO_MISCONCEPTION and unknown labels are not counted
        source = row.get("dataset_source") or "?"
        bucket = "certain" if _is_certain(row) else "silver"
        e = entry(label)
        e[bucket] += 1
        lane = e["by_lane"].setdefault(source, {"certain": 0, "silver": 0})
        lane[bucket] += 1

    for e in stats.values():
        e["under_floor"] = e["certain"] < e["floor"]
    return stats


def _print_per_class_report(stats: dict[str, dict[str, Any]]) -> None:
    print("\n=== Layer-2 per-class report (class x lane x certain/silver) ===")
    header = f"{'class':<24} {'certain':>7} {'silver':>7} {'floor':>6}  status"
    print(header)
    print("-" * len(header))
    for label in CERTAIN_FLOOR:
        e = stats.get(label, {"certain": 0, "silver": 0, "floor": CERTAIN_FLOOR[label], "under_floor": True})
        status = "UNDER" if e["under_floor"] else "ok"
        print(f"{label:<24} {e['certain']:>7} {e['silver']:>7} {e['floor']:>6}  {status}")
        for source in sorted(e.get("by_lane", {})):
            lane = e["by_lane"][source]
            print(f"    {source:<20} certain={lane['certain']:<5} silver={lane['silver']}")


# ------------------------------------------------------------------ CLI


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[RowIssue]]:
    """Read a JSONL file. Malformed lines become parse issues, never raise."""
    rows: list[dict[str, Any]] = []
    issues: list[RowIssue] = []
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(RowIssue(check="json", row_id=f"{path.name}:{lineno}", detail=str(exc)))
            continue
        if not isinstance(obj, dict):
            issues.append(RowIssue(check="json", row_id=f"{path.name}:{lineno}", detail="line is not a JSON object"))
            continue
        rows.append(obj)
    return rows, issues


def _dataset_jsonl_files(dataset_dir: Path) -> list[Path]:
    """Prefer annotations/*.jsonl (real layout); else scan the dir directly."""
    annotations = dataset_dir / "annotations"
    search = annotations if annotations.is_dir() else dataset_dir
    return sorted(search.glob("*.jsonl"))


def load_normalized_ids(
    ids_path: Path | None = None, csv_path: Path | None = None
) -> set[str]:
    """Load the normalized `source_record_id` join column.

    `ids_path` is a text file, one id per line. `csv_path` reads the
    `source_record_id` column of the normalized submissions index.
    """
    if ids_path is not None:
        return {
            line.strip()
            for line in ids_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    if csv_path is not None:
        ids: set[str] = set()
        with csv_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                value = (row.get("source_record_id") or "").strip()
                if value:
                    ids.add(value)
        return ids
    return set()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--normalized-ids", type=Path, default=None,
                        help="text file: one source_record_id per line")
    parser.add_argument("--normalized-csv", type=Path, default=None,
                        help="normalized submissions.csv (reads source_record_id column)")
    parser.add_argument("--proofs-dir", type=Path, default=None,
                        help="mutant-proof corpus dir (SYNTHETIC proof-join); "
                             "defaults to <dataset-dir>/annotations/mutant_proofs")
    parser.add_argument("--per-class-report", action="store_true")
    args = parser.parse_args(argv)

    if args.normalized_ids is None and args.normalized_csv is None:
        args.normalized_csv = DEFAULT_NORMALIZED_CSV

    files = _dataset_jsonl_files(args.dataset_dir)
    if not files:
        print(f"FAIL  no annotation JSONL found under {args.dataset_dir}")
        return 1

    normalized_ids = load_normalized_ids(args.normalized_ids, args.normalized_csv)

    # Never let an empty join column silently pass G1 — that would report
    # "0 orphans" having checked nothing (a false green).
    if not normalized_ids:
        print(f"FAIL  normalized join column empty — cannot verify labels<->normalized join")
        print(f"      (looked at: {args.normalized_ids or args.normalized_csv})")
        return 1

    all_rows: list[dict[str, Any]] = []
    all_issues: list[RowIssue] = []
    for path in files:
        rows, parse_issues = load_jsonl(path)
        all_rows.extend(rows)
        all_issues.extend(parse_issues)

    proofs_dir = args.proofs_dir or (args.dataset_dir / "annotations" / "mutant_proofs")
    proof_keys = load_proof_keys(proofs_dir)

    report = verify(all_rows, normalized_ids, proof_keys=proof_keys)
    report.issues = all_issues + report.issues

    print(f"rows scanned: {report.n_rows} across {len(files)} file(s)")
    print(f"normalized join ids loaded: {len(normalized_ids)}")
    if proof_keys:
        print(f"mutant proof keys loaded: {len(proof_keys)} (from {proofs_dir})")
    if report.issues:
        print(f"G1 FAIL - {len(report.issues)} issue(s):")
        for issue in report.issues:
            print(f"  [{issue.check}] {issue.row_id}: {issue.detail}")
    else:
        print("G1 PASS - 0 orphans, enums clean, schema_version present")

    if args.per_class_report:
        _print_per_class_report(per_class_report(all_rows))

    return 1 if report.issues else 0


if __name__ == "__main__":
    sys.exit(main())
