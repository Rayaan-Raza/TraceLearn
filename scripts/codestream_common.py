"""Shared CodeStream loading for Lane B (Umaima).

Reads the raw CodeStream CSVs (read-only) and, when present, the normalized
index so every row carries the repo-wide ``submission_id`` / ``problem_id``.

Raw location, first match wins:
  --raw argument · $TRACELEARN_RAW · G:\\TraceLearn\\Datasets_RAW ·
  ~/Downloads/TraceLearn/TraceLearn/Datasets_RAW
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

csv.field_size_limit(2**31 - 1)

ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "data" / "misconception_dataset"
CS_DIRNAME = "CodeStream A Dataset of Iterative Programming Subm"
RAW_CANDIDATES = [
    os.environ.get("TRACELEARN_RAW"),
    r"G:\TraceLearn\Datasets_RAW",
    str(Path.home() / "Downloads" / "TraceLearn" / "TraceLearn" / "Datasets_RAW"),
]
C_FAMILY = {"c", "c++"}
TAXONOMY_VERSION = "tl-cpp-v2"
SCHEMA_VERSION = "1.0"


def find_raw(raw: str | None = None) -> Path:
    for cand in [raw, *RAW_CANDIDATES]:
        if cand and (Path(cand) / CS_DIRNAME / "Submission Data.csv").exists():
            return Path(cand)
    raise FileNotFoundError(
        "CodeStream raw CSVs not found. Pass --raw <Datasets_RAW> or set TRACELEARN_RAW.")


def user_hash(user_id: str) -> str:
    return hashlib.sha256(f"codestream:{user_id}".encode()).hexdigest()[:16]


def code_sha(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


@dataclass
class Problem:
    problem_id: str  # normalized id, e.g. tl-codestream-prob_006
    source_problem_id: str  # prob_006
    statement: str
    tests: list[dict]  # [{"input", "output"}]


@dataclass
class Submission:
    submission_id: str  # normalized id
    source_submission_id: str
    problem_id: str
    source_problem_id: str
    user_id: str
    attempt_number: int
    language: str  # "c" | "cpp"
    code: str
    verdict: str
    verdict_trace: list = field(default_factory=list)

    @property
    def lang(self) -> str:
        return self.language


def _norm_problem_id(pid: str) -> str:
    return f"tl-codestream-{pid}"


def _norm_submission_id(sid: str) -> str:
    return f"tl-codestream-sub-{sid}"


def load_problems(raw: Path) -> dict[str, Problem]:
    out = {}
    with open(raw / CS_DIRNAME / "Problem Data.csv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            tests = json.loads(row["evaluation_test_cases"]) if row["evaluation_test_cases"] else []
            tests = sorted(tests, key=lambda t: t.get("test_case_no", 0))
            p = Problem(problem_id=_norm_problem_id(row["problem_id"]),
                        source_problem_id=row["problem_id"],
                        statement=row["problem_description"] or "",
                        tests=[{"input": t["input"], "output": t["output"]} for t in tests])
            out[p.problem_id] = p
    return out


def load_submissions(raw: Path, c_family_only: bool = True) -> list[Submission]:
    out = []
    with open(raw / CS_DIRNAME / "Submission Data.csv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            lang = row["programming_language"].strip().lower()
            if c_family_only and lang not in C_FAMILY:
                continue
            try:
                trace = json.loads(row["verdict_sequence_trace"] or "[]")
            except json.JSONDecodeError:
                trace = []
            out.append(Submission(
                submission_id=_norm_submission_id(row["submission_id"]),
                source_submission_id=row["submission_id"],
                problem_id=_norm_problem_id(row["problem_id"]),
                source_problem_id=row["problem_id"],
                user_id=row["user_id"],
                attempt_number=int(row["attempt_number"] or 0),
                language="cpp" if lang == "c++" else lang,
                code=row["source_code"],
                verdict=row["final_verdict"],
                verdict_trace=trace,
            ))
    return out


def previous_submission_index(subs: list[Submission]) -> dict[str, str | None]:
    """submission_id -> previous attempt's submission_id by the same user on the same problem."""
    by_key: dict[tuple, list[Submission]] = {}
    for s in subs:
        by_key.setdefault((s.user_id, s.problem_id), []).append(s)
    prev = {}
    for group in by_key.values():
        group.sort(key=lambda s: s.attempt_number)
        last = None
        for s in group:
            prev[s.submission_id] = last
            last = s.submission_id
    return prev


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")
            n += 1
    os.replace(tmp, path)
    return n
