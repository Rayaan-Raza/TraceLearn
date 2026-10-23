#!/usr/bin/env python3
"""Label the PROGpedia lane with pg weak rules -> annotations/tier1b_progpedia.jsonl (R-I6, plan §3.4).

Rules (plan-pinned conjunctions; a rule fires only when EVERY signal holds):
    pg-1  verdict != ACCEPTED  and  -Wparentheses      and assign-in-condition feeds output
    pg-2  verdict == RUNTIME_ERROR                     and unguarded recursion
    pg-3  verdict == RUNTIME_ERROR                     and array write beyond fixed size
    pg-4  verdict != ACCEPTED  and  -Wmaybe-uninitialized and use-before-init marker

Scope: PROGPEDIA x language in {c, cpp} (Java excluded by directive; Python has
no compiler warnings and no fixed-size semantics). One label per row; several
rules for DIFFERENT classes never force-pick — the row goes to the multi_signal
review pool (§3.2). Rows with no fire stay unlabeled (never OTHER_ERROR).

`label_confidence` ships at the §3.4 cap (0.60/0.55) as the provisional value;
§3.5's Beta-bound replaces it once the >=50-fire precision audit runs (G5).

CLI:
    python scripts/label_weak_progpedia.py [--out annotations/tier1b_progpedia.jsonl]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tracelearn_features.extractor import extract_features  # noqa: E402
from tracelearn_features.schema import SCHEMA_VERSION  # noqa: E402
from tracelearn_features.taxonomy import TAXONOMY_VERSION  # noqa: E402

from scripts.parse_cpg import cpg_features, parse_submission  # noqa: E402

DEFAULT_INDEX = ROOT / "data/Data_from_Datasets/intermediate/normalized/submissions/submissions.csv"
DEFAULT_PROBLEMS = ROOT / "data/Data_from_Datasets/intermediate/normalized/problems/problems.csv"
DEFAULT_WARNINGS = ROOT / "data/misconception_dataset/features/progpedia_warnings.csv"
DEFAULT_RAW_ROOT = Path(r"G:\TraceLearn\Datasets_RAW")
# under the dataset dir so verify_dataset's default scan picks it up (§7 tree)
DEFAULT_OUT = ROOT / "data/misconception_dataset/annotations/tier1b_progpedia.jsonl"
DEFAULT_REVIEW_OUT = ROOT / "data/misconception_dataset/review/multi_signal.jsonl"

# rule -> (label, confidence cap per plan §3.4).
RULES: dict[str, tuple[str, float]] = {
    "pg-1": ("CPP_ASSIGN_VS_COMPARE", 0.60),
    "pg-2": ("CPP_MISSING_BASE_CASE", 0.60),
    "pg-3": ("CPP_ARRAY_BOUNDS", 0.60),
    "pg-4": ("CPP_UNINITIALIZED_VAR", 0.55),
}
PG_LANGUAGES = ("c", "cpp")
PIPELINE_RUN_ID = "label_weak_progpedia/1.0.0"


# ------------------------------------------------------------------- signals


def _flag_set(flags: Any) -> set[str]:
    """Normalized flag names with count > 0. None / malformed -> empty (§6:
    absent evidence can never satisfy a warning signal)."""
    if not isinstance(flags, (list, tuple)):
        return set()
    out: set[str] = set()
    for item in flags:
        if isinstance(item, dict) and item.get("flag") and (item.get("count") or 0) > 0:
            out.add(str(item["flag"]))
    return out


def fire_rules(verdict: Any, flags: Any, feats: dict[str, Any]) -> list[str]:
    """pg rules whose full conjunction holds (deterministic rule order)."""
    fs = _flag_set(flags)
    non_accepted = bool(verdict) and verdict != "ACCEPTED"
    runtime_error = verdict == "RUNTIME_ERROR"

    def hits(name: str) -> bool:
        return (feats.get(name) or 0) > 0

    fired: list[str] = []
    if non_accepted and "-Wparentheses" in fs and hits("assign_in_condition_count") \
            and hits("assign_feeds_output_count"):
        fired.append("pg-1")
    if runtime_error and hits("unguarded_recursion_count"):
        fired.append("pg-2")
    if runtime_error and hits("array_write_oob_count"):
        fired.append("pg-3")
    if non_accepted and "-Wmaybe-uninitialized" in fs and hits("use_before_init_count"):
        fired.append("pg-4")
    return fired


# ------------------------------------------------------------------ context


def _as_int(value: Any) -> int | None:
    try:
        return int(float(value)) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _context_from_problem(problem: dict[str, Any] | None) -> dict[str, Any] | None:
    """context-block evidence from problems.csv (§6: absent -> None -> NaN)."""
    if not problem:
        return None
    statement = problem.get("statement_text") or problem.get("statement")
    tests_raw = problem.get("sample_tests")
    tags = problem.get("concept_tags")
    if isinstance(tags, str) and tags.strip():
        try:
            tags = json.loads(tags)
        except (ValueError, TypeError):
            tags = None
    elif not isinstance(tags, (list, tuple)):
        tags = None
    return {
        "statement": statement if isinstance(statement, str) and statement.strip() else None,
        "sample_test_count": _as_int(problem.get("sample_test_count")),
        "sample_tests_present": bool(tests_raw and str(tests_raw).strip()),
        "has_constraints": bool(problem.get("constraints") and str(problem.get("constraints")).strip()),
        "difficulty": _as_float(problem.get("difficulty")),
        "concept_tags": list(tags) if tags else None,
        "cpp_submission_count": _as_int(problem.get("cpp_submission_count")),
    }


# ------------------------------------------------------------------ labeling


def _load_cpg(raw_root: Path, idx_row: dict[str, Any]):
    """Parse the submission's shipped CPG. Returns (graph, skip_reason)."""
    path = raw_root / str(idx_row.get("source_code_path") or "")
    if not path.is_file():
        return None, "missing_source"
    dsc_files = sorted(path.parent.glob("*.dsc.csv"))
    if not dsc_files:
        return None, "no_cpg"
    cpg_files = sorted(path.parent.glob("*.cpg.csv"))
    graph = parse_submission(cpg_files[0] if cpg_files else path.parent / "none.cpg.csv",
                             dsc_files[0])
    if graph is None or graph.node_count == 0:
        return None, "unparsed"
    return graph, None


def build_row(idx_row: dict[str, Any], seq: int, feats: dict[str, Any],
              warnings_list: list[dict] | None, context: dict[str, Any] | None,
              source_text: str, rules: list[str]) -> dict[str, Any]:
    """One tier1b dataset row (plan §3.2 shape)."""
    label = RULES[rules[0]][0]
    confidence = max(RULES[r][1] for r in rules)
    row: dict[str, Any] = {
        "row_id": f"pg-{seq:06d}",
        "dataset_source": "PROGPEDIA",
        "source_record_id": idx_row["source_record_id"],
        "problem_id": idx_row["problem_id"],
        # cluster comes from the merge's grouped split (Task 8), never guessed here
        "problem_cluster": None,
        "language": idx_row["language"],
        "label": label,
        "label_source": "weak_rule",
        "label_confidence": confidence,
        "secondary_labels": [],
        "verdict": idx_row.get("source_verdict"),
        "firing_functions": list(rules),
        "seed_ref": None,
        "mutation_op": None,
        "verified_by_execution": None,
        "meta": {"user_id_hash": None, "attempt_index": None,
                 "timestamp": None, "prev_submission_id": None},
    }
    row.update(extract_features(
        source_text,
        idx_row["language"],
        warnings=warnings_list,
        runtime=None,        # PROGPedia ships no sanitizer/valgrind evidence
        tests=None,          # ... and no test execution evidence
        cpg=feats,
        context=context,
    ))
    row["pipeline_run_id"] = PIPELINE_RUN_ID
    row["taxonomy_version"] = TAXONOMY_VERSION
    row["schema_version"] = SCHEMA_VERSION
    return row


def label_rows(
    index_rows: list[dict[str, Any]],
    problems_by_id: dict[str, dict[str, Any]],
    warnings_by_id: dict[str, list[dict] | None],
    raw_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Apply pg rules to every in-scope row.

    Returns (labeled rows sorted by source_record_id, multi_signal review pool,
    skipped counts). Never guesses: absent CPG/warnings -> no fire.
    """
    skipped: dict[str, int] = {}
    labeled: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []

    def bump(key: str) -> None:
        skipped[key] = skipped.get(key, 0) + 1

    ordered = sorted(index_rows, key=lambda r: str(r.get("source_record_id")))
    seq = 0
    for idx_row in ordered:
        if idx_row.get("dataset_source") != "PROGPEDIA":
            continue
        if idx_row.get("language") not in PG_LANGUAGES:
            bump("out_of_scope")
            continue
        graph, skip = _load_cpg(raw_root, idx_row)
        if graph is None:
            bump(skip or "no_cpg")
            continue
        feats = cpg_features(graph)
        warnings_list = warnings_by_id.get(str(idx_row.get("source_record_id")))
        fired = fire_rules(idx_row.get("source_verdict"), warnings_list, feats)
        if not fired:
            bump("no_rule_fired")
            continue
        labels = {RULES[r][0] for r in fired}
        if len(labels) > 1:
            # §3.2: different classes -> review pool, never force-picked
            review.append({
                "source_record_id": idx_row["source_record_id"],
                "problem_id": idx_row.get("problem_id"),
                "language": idx_row.get("language"),
                "verdict": idx_row.get("source_verdict"),
                "source_code_path": idx_row.get("source_code_path"),
                "firing_functions": list(fired),
                "candidate_labels": sorted(labels),
            })
            bump("multi_signal")
            continue
        seq += 1
        source_path = raw_root / str(idx_row.get("source_code_path") or "")
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
        context = _context_from_problem(problems_by_id.get(str(idx_row.get("problem_id"))))
        labeled.append(build_row(idx_row, seq, feats, warnings_list, context,
                                 source_text, fired))
    return labeled, review, skipped


# ----------------------------------------------------------------------- CLI


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", errors="replace", newline="") as fh:
        return list(csv.DictReader(fh))


def load_warnings(path: Path) -> dict[str, list[dict] | None]:
    """progpedia_warnings.csv -> {source_record_id: flags list or None}."""
    out: dict[str, list[dict] | None] = {}
    if not path.is_file():
        return out
    for r in read_csv(path):
        raw_flags = r.get("flags")
        out[str(r.get("source_record_id"))] = json.loads(raw_flags) if raw_flags else None
    return out


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    ap.add_argument("--problems", type=Path, default=DEFAULT_PROBLEMS)
    ap.add_argument("--warnings", type=Path, default=DEFAULT_WARNINGS)
    ap.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--review-out", type=Path, default=DEFAULT_REVIEW_OUT)
    args = ap.parse_args(argv)

    index_rows = [r for r in read_csv(args.index)
                  if r.get("dataset_source") == "PROGPEDIA"]
    problems = {str(r.get("problem_id")): r for r in read_csv(args.problems)}
    warnings = load_warnings(args.warnings)

    labeled, review, skipped = label_rows(index_rows, problems, warnings, args.raw_root)
    write_jsonl(labeled, args.out)
    write_jsonl(review, args.review_out)

    from collections import Counter
    per_label = Counter(r["label"] for r in labeled)
    print(f"progpedia index rows={len(index_rows)}")
    print("skipped:", ", ".join(f"{k}={v}" for k, v in sorted(skipped.items())) or "none")
    print(f"labeled={len(labeled)}  multi_signal_review={len(review)}")
    for label, n in sorted(per_label.items()):
        print(f"  {label}: {n}")
    print(f"wrote {args.out}")
    print(f"wrote {args.review_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
