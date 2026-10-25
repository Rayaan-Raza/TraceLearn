#!/usr/bin/env python3
"""TraceLearn source ingestion adapter.

Reads raw datasets. Writes normalized JSONL records.
Reads raw files only. It never changes a raw file.

Run:
    python scripts/ingest_sources.py
    python scripts/ingest_sources.py --with-submissions --inline-code
    python scripts/ingest_sources.py --sources codestream --exclude-without-tests

Output layout (Master Plan section 4):
    data/intermediate/normalized/
      README.md
      ingest_run_manifest.json
      hash_cache.json
      problems/problems.jsonl
      problems/problems.csv
      problems/README.md
      submissions/submissions.jsonl
      submissions/submissions.csv
      submissions/README.md
      exclusions/exclusions.jsonl
      exclusions/exclusions.csv
      exclusions/README.md

Every table ships as JSONL and CSV. Every folder ships a README.

Rules:
1. Keep source identifiers in every record.
2. Convert text to UTF-8 and clean whitespace.
3. Extract sample test inputs and sample test outputs.
4. Log every excluded record with one exclusion reason.
5. Emit both naming conventions, Master Plan and Agent Brief.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

PARSER_VERSION = "ingest_sources.py/1.1.0"
RAW_ROOT = Path(r"G:\TraceLearn\Datasets_RAW")
# Master Plan section 4 layout.
DEFAULT_OUT = Path(r"G:\TraceLearn\data\intermediate\normalized")

CODE_EXTENSIONS = {
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".java": "java",
    ".py": "python",
    ".cs": "csharp",
    ".js": "javascript",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".kt": "kotlin",
    ".ts": "typescript",
    ".php": "php",
    ".scala": "scala",
    ".hs": "haskell",
    ".pl": "perl",
    ".lua": "lua",
}

SOURCE_SLUG = {
    "PROJECT_CODENET": "codenet",
    "CODESTREAM": "codestream",
    "PROGPEDIA": "progpedia",
}

# Section names the markdown parser treats as headings.
SECTION_WORDS = {
    "task",
    "input",
    "input format",
    "output",
    "output format",
    "example",
    "examples",
    "sample",
    "sample input",
    "sample output",
    "constraints",
    "constraint",
    "limits",
    "limit",
}


# --------------------------------------------------------------------------
# text helpers
# --------------------------------------------------------------------------


class TextDecodeError(Exception):
    """Raised when a file has no supported character encoding."""


def decode_bytes(data: bytes) -> tuple[str, str]:
    """Return text and encoding name. Raise TextDecodeError on failure."""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise TextDecodeError("no supported encoding matched the byte stream")


def read_text(path: Path) -> tuple[str, str]:
    """Read a file and return text plus encoding name."""
    return decode_bytes(path.read_bytes())


def clean_text(text: str) -> str:
    """Normalize unicode, line breaks and whitespace runs."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\ufeff", "")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of a byte string."""
    return hashlib.sha256(data).hexdigest()


def nonempty(text: str | None) -> str | None:
    """Return cleaned text, or None when the text has no visible content."""
    if not text:
        return None
    cleaned = clean_text(text)
    return cleaned or None


def one_line(text: str, limit: int = 0) -> str:
    """Return a single spaced line. Cut the line at limit characters."""
    out = re.sub(r"\s+", " ", clean_text(text)).strip()
    if limit and len(out) > limit:
        return out[: limit - 1] + "..."
    return out


def rel_ref(path: Path) -> str:
    """Return a stable reference path relative to the raw root."""
    try:
        return path.relative_to(RAW_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


# --------------------------------------------------------------------------
# exclusion log
# --------------------------------------------------------------------------


@dataclass
class ExclusionLog:
    """Collects every record the adapter refuses to write."""

    run_id: str
    rows: list[dict[str, Any]] = field(default_factory=list)

    def add(
        self,
        source_dataset: str,
        record_ref: str,
        stage: str,
        reason: str,
        detail: str = "",
    ) -> None:
        """Append one exclusion row."""
        self.rows.append(
            {
                "run_id": self.run_id,
                "source_dataset": source_dataset,
                "record_ref": record_ref,
                "stage": stage,
                "exclusion_reason": reason,
                "detail": one_line(detail, 300),
            }
        )

    def count_by_reason(self) -> dict[str, int]:
        """Return exclusion counts keyed by reason."""
        out: dict[str, int] = {}
        for row in self.rows:
            out[row["exclusion_reason"]] = out.get(row["exclusion_reason"], 0) + 1
        return dict(sorted(out.items()))


# --------------------------------------------------------------------------
# markdown section parser
# --------------------------------------------------------------------------


def split_markdown_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Split markdown text into a title and a section list.

    Returns (title, [(heading, body), ...]). The first block uses
    heading "" for text before any heading.
    """
    lines = text.split("\n")
    title = ""
    blocks: list[tuple[str, list[str]]] = [("", [])]
    i = 0
    while i < len(lines):
        line = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        setext = re.fullmatch(r"={3,}\s*", nxt) or re.fullmatch(r"-{3,}\s*", nxt)
        atx = re.match(r"^#{1,6}\s+(.*)$", line)
        bold = re.fullmatch(r"\*\*([^*]{1,80})\*\*\s*", line.strip())
        if setext and line.strip():
            heading = line.strip().lstrip("#").strip()
            if not title and not blocks[0][1] and not blocks[0][0]:
                title = heading
                blocks[0] = (heading, [])
            else:
                blocks.append((heading, []))
            i += 2
            continue
        if atx:
            heading = atx.group(1).strip()
            if not title and not blocks[0][1]:
                title = heading
                blocks[0] = (heading, [])
            else:
                blocks.append((heading, []))
            i += 1
            continue
        if bold:
            heading = bold.group(1).strip()
            if heading.lower().strip(":") in SECTION_WORDS:
                if len(blocks) == 1 and not blocks[0][0] and not blocks[0][1]:
                    blocks[0] = (heading, [])
                else:
                    blocks.append((heading, []))
                i += 1
                continue
        blocks[-1][1].append(line)
        i += 1
    out = [(h, clean_text("\n".join(body))) for h, body in blocks]
    if not title and out and out[0][0]:
        title = out[0][0]
    return title, out


def strip_sample_block(text: str) -> str:
    """Cut a description at the first sample table or sample heading."""
    if not text:
        return text
    cut = len(text)
    for match in re.finditer(
        r"^\s*\|?\s*#{0,6}\s*sample\s+(input|output)\b.*$",
        text,
        re.I | re.M,
    ):
        cut = min(cut, match.start())
        break
    return clean_text(text[:cut])


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    """Return (label, content) for every fenced code block.

    The label is the nearest heading word before the block.
    """
    out: list[tuple[str, str]] = []
    pattern = re.compile(r"```[^\n]*\n(.*?)```", re.S)
    for match in pattern.finditer(text):
        prefix = text[: match.start()]
        label = ""
        for line in reversed(prefix.split("\n")):
            stripped = line.strip()
            if not stripped:
                continue
            head = re.match(r"^#{1,6}\s*(.*)$", stripped)
            bold = re.match(r"^\*\*(.*)\*\*$", stripped)
            plain = stripped.lstrip("#").strip().rstrip(":")
            if head:
                label = head.group(1)
            elif bold:
                label = bold.group(1)
            elif len(plain) <= 40 and re.fullmatch(r"[A-Za-z][A-Za-z0-9 /_-]*", plain):
                label = plain
            break
        out.append((one_line(label, 60), match.group(1).strip("\n")))
    return out


def md_table_pairs(text: str) -> list[tuple[str, str]]:
    """Return (input, output) rows from a two column markdown table."""
    rows: list[list[str]] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.count("|") < 3:
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue
        rows.append(cells)
    if len(rows) < 2:
        return []
    header = [c.lower() for c in rows[0]]
    pairs: list[tuple[str, str]] = []
    for cells in rows[1:]:
        pairs.append((cells[0], cells[1] if len(cells) > 1 else ""))
    return pairs


def build_sample_tests(
    input_blocks: list[str], output_blocks: list[str], table_pairs: list[tuple[str, str]]
) -> list[dict[str, Any]]:
    """Pair sample inputs and outputs into test case records."""
    tests: list[dict[str, Any]] = []
    for idx, (inp, out) in enumerate(zip(input_blocks, output_blocks), start=1):
        tests.append(
            {
                "test_index": idx,
                "test_source": "statement_sample",
                "input": inp,
                "expected_output": out,
            }
        )
    if not tests:
        for idx, (inp, out) in enumerate(table_pairs, start=1):
            tests.append(
                {
                    "test_index": idx,
                    "test_source": "statement_table",
                    "input": inp,
                    "expected_output": out,
                }
            )
    return tests


def label_is(label: str, kind: str) -> bool:
    """Check whether a heading label names an input or an output block."""
    low = one_line(label).lower()
    if kind == "input":
        return bool(re.search(r"\binput\b", low)) and not re.search(
            r"\boutput\b", low
        )
    return bool(re.search(r"\boutput\b", low)) and not re.search(r"\binput\b", low)


# --------------------------------------------------------------------------
# HTML section parser (Project CodeNet)
# --------------------------------------------------------------------------


class _HtmlSectionParser(HTMLParser):
    """Collect heading and body events from one problem statement."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: list[tuple[str, str]] = []
        self._tag = ""
        self._buf: list[str] = []

    def _flush(self) -> None:
        if self._tag and self._buf:
            self.events.append((self._tag, "".join(self._buf)))
        self._buf = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        self._flush()
        if tag in {"h1", "h2", "h3", "h4", "p", "pre", "li"}:
            self._tag = tag
        else:
            self._tag = ""
        if tag == "br":
            self._buf.append("\n")
        if tag in {"p", "pre", "div", "tr"}:
            self._buf.append("\n")

    def handle_endtag(self, tag: str) -> None:
        self._flush()
        self._tag = ""

    def handle_data(self, data: str) -> None:
        self._buf.append(data)


def parse_html_statement(raw_html: str) -> dict[str, Any]:
    """Parse one CodeNet statement into title, sections and sample tests."""
    parser = _HtmlSectionParser()
    parser.feed(raw_html)
    parser.close()
    parser._flush()

    title = ""
    first_heading = ""
    sections: list[tuple[str, list[str]]] = [("", [])]
    for tag, data in parser.events:
        text = clean_text(data)
        if not text:
            continue
        if tag in {"h1", "h2", "h3", "h4"} and not first_heading:
            first_heading = one_line(text)
        if tag == "h1" and not title:
            title = one_line(text)
            continue
        if tag in {"h2", "h3", "h4"}:
            sections.append((one_line(text), []))
            continue
        sections[-1][1].append(text)

    named = [(h, "\n".join(b).strip()) for h, b in sections]

    def collect(pattern: str) -> list[str]:
        rx = re.compile(pattern, re.I)
        return [body for head, body in named if rx.search(head) and body]

    input_blocks = collect(r"^sample input") or collect(r"^input for")
    output_blocks = collect(r"^sample output") or collect(r"^output for the sample")

    if not input_blocks:
        input_blocks = collect(r"^sample input")
    if not output_blocks:
        output_blocks = collect(r"^sample output")

    tests = build_sample_tests(input_blocks, output_blocks, [])

    def first_body(*patterns: str) -> str:
        for head, body in named:
            for pat in patterns:
                if re.search(pat, head, re.I) and body:
                    return body
        return ""

    statement_parts = [body for head, body in named if body]
    return {
        "title": title or first_heading,
        "statement_text": clean_text("\n\n".join(statement_parts)),
        "input_description": first_body(r"^input$", r"^input format$"),
        "output_description": first_body(r"^output$", r"^output format$"),
        "constraints": first_body(r"^constraints?$", r"^limit$"),
        "sample_tests": tests,
        "sections": [head for head, _body in named if head],
    }


# --------------------------------------------------------------------------
# generic record builders
# --------------------------------------------------------------------------


def make_problem_id(source_dataset: str, source_problem_id: str) -> str:
    """Return a stable canonical problem id."""
    return f"tl-{SOURCE_SLUG.get(source_dataset, source_dataset.lower())}-{source_problem_id}"


def make_submission_id(source_dataset: str, source_submission_id: str) -> str:
    """Return a stable canonical submission id."""
    slug = SOURCE_SLUG.get(source_dataset, "x")
    return f"tl-{slug}-sub-{source_submission_id}"


def make_provenance_id(provenance_ref: str) -> str:
    """Return a short stable provenance key."""
    return "PROV-" + sha256_bytes(provenance_ref.encode("utf-8"))[:12]


def base_problem(
    *,
    source_dataset: str,
    source_problem_id: str,
    run_id: str,
    provenance_ref: str,
    source_sha256: str,
    statement_format: str,
) -> dict[str, Any]:
    """Return the common problem record skeleton.

    Emits both naming conventions. The Master Plan section 5.1 names
    come first. The Agent Brief section 5.1 names follow as aliases.
    """
    pid = make_problem_id(source_dataset, source_problem_id)
    prov = make_provenance_id(provenance_ref)
    return {
        "record_type": "problem",
        # Master Plan section 5.2 "problems" table.
        "problem_id": pid,
        "dataset_source": source_dataset,
        "source_dataset": source_dataset,
        "source_problem_id": source_problem_id,
        "title": None,
        "statement": None,
        "statement_text": None,
        "input_spec": None,
        "input_description": None,
        "output_spec": None,
        "output_description": None,
        "constraints": None,
        "concept_tags": None,
        "difficulty": None,
        "sample_tests": [],
        "sample_test_count": 0,
        "language_scope": None,
        "statement_format": statement_format,
        "source_url": None,
        "source_license": None,
        "source_encoding": None,
        "provenance_id": prov,
        "provenance_ref": provenance_ref,
        "source_sha256": source_sha256,
        "parser_version": PARSER_VERSION,
        "ingestion_run_id": run_id,
    }


def base_submission(
    *,
    source_dataset: str,
    source_submission_id: str,
    source_problem_id: str,
    run_id: str,
    provenance_ref: str,
    language: str,
) -> dict[str, Any]:
    """Return the common submission record skeleton.

    Emits both naming conventions. The Master Plan section 5.1 names
    come first. The Agent Brief section 5.2 names follow as aliases.
    """
    sid = make_submission_id(source_dataset, source_submission_id)
    prov = make_provenance_id(provenance_ref)
    return {
        "record_type": "submission",
        # Master Plan section 5.1 "submissions" table.
        "submission_id": sid,
        "dataset_source": source_dataset,
        "source_dataset": source_dataset,
        "source_record_id": source_submission_id,
        "source_submission_id": source_submission_id,
        "source_problem_id": source_problem_id,
        "problem_id": make_problem_id(source_dataset, source_problem_id),
        "source_learner_id": None,
        "learner_id": None,
        "attempt_order": None,
        "attempt_number": None,
        "timestamp": None,
        "submitted_at": None,
        "language": language,
        "language_standard": None,
        "source_code_path": provenance_ref,
        "source_code_ref": provenance_ref,
        "source_code": None,
        "source_code_sha256": None,
        "compile_status": None,
        "runtime_status": None,
        "correct": None,
        "source_verdict": None,
        "source_verdict_definition": None,
        "tracelearn_label": None,
        "misconception_label": None,
        "label_status": "unlabelled",
        "annotation_status": "unlabelled",
        "label_confidence": None,
        "state_label": None,
        "split": None,
        "is_synthetic": False,
        "provenance_id": prov,
        "provenance_ref": provenance_ref,
        "parser_version": PARSER_VERSION,
        "ingestion_run_id": run_id,
    }


class HashCache:
    """Reuse SHA-256 values across runs for unchanged files.

    Hashing 139,799 C++ files takes about 45 minutes on this machine.
    The cache keys each hash on relative path, size and mtime, so a
    later run only hashes files that actually changed.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.entries: dict[str, dict[str, int | str]] = {}
        self.hits = 0
        self.misses = 0
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.entries = loaded
            except (OSError, json.JSONDecodeError):
                self.entries = {}

    @staticmethod
    def _key(rel_path: str, size: int, mtime_ns: int) -> str:
        return f"{rel_path}|{size}|{mtime_ns}"

    def hash_file(self, path: Path, data: bytes) -> str:
        """Return the SHA-256 for one file, using the cache when valid."""
        ref = rel_ref(path)
        try:
            stat = path.stat()
        except OSError:
            return sha256_bytes(data)

        key = self._key(ref, stat.st_size, stat.st_mtime_ns)
        cached = self.entries.get(ref)
        if cached and cached.get("key") == key:
            self.hits += 1
            return str(cached["digest"])

        self.misses += 1
        digest = sha256_bytes(data)
        self.entries[ref] = {"key": key, "digest": digest}
        return digest

    def save(self) -> None:
        """Write the cache to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.entries, ensure_ascii=False), encoding="utf-8"
        )


# Master Plan section 5.1 vocabulary for label_status.
LABEL_UNLABELLED = "unlabelled"
LABEL_SOURCE = "source_label"

ACCEPTED_TOKENS = {"accepted", "accept", "correct"}
COMPILE_ERROR_TOKENS = {"compilation error", "compile error", "ce"}
TIMEOUT_TOKENS = {"time limit exceeded", "tle"}
RUNTIME_ERROR_TOKENS = {"runtime error", "runtime_error", "re"}
MEMORY_LIMIT_TOKENS = {"memory limit exceeded", "memory_limit_exceeded", "mle"}


def apply_outcome(sub: dict[str, Any], verdict: str | None) -> None:
    """Fill outcome and label fields from one source verdict string.

    A source verdict is an outcome, not a misconception label. This
    function never sets tracelearn_label.
    """
    if not verdict:
        sub["label_status"] = LABEL_UNLABELLED
        sub["annotation_status"] = LABEL_UNLABELLED
        return

    token = verdict.strip().lower()
    sub["label_status"] = LABEL_SOURCE
    sub["annotation_status"] = LABEL_SOURCE

    if token in ACCEPTED_TOKENS:
        sub["correct"] = True
        sub["compile_status"] = "success"
        sub["runtime_status"] = "success"
    elif token in COMPILE_ERROR_TOKENS:
        sub["correct"] = False
        sub["compile_status"] = "error"
        sub["runtime_status"] = "unavailable"
    elif token in TIMEOUT_TOKENS:
        sub["correct"] = False
        sub["compile_status"] = "success"
        sub["runtime_status"] = "timeout"
    elif token in RUNTIME_ERROR_TOKENS:
        sub["correct"] = False
        sub["compile_status"] = "success"
        sub["runtime_status"] = "error"
    elif token in MEMORY_LIMIT_TOKENS:
        sub["correct"] = False
        sub["compile_status"] = "success"
        sub["runtime_status"] = "memory_limit"
    else:
        # Wrong answer, presentation error and output limit errors imply
        # the program built and ran. The judge states no more than that.
        sub["correct"] = False
        sub["compile_status"] = "success"
        sub["runtime_status"] = "completed"


class SubmissionsWriter:
    """Write submission rows to disk as they are produced.

    Holds no row list in memory. The CodeNet C++ walk produces 139,799
    rows, and this machine has about 1.2 GB of free RAM. Buffering those
    rows killed an earlier run. Writing each row immediately keeps peak
    memory flat.
    """

    def __init__(self, outdir: Path, fieldnames: list[str]) -> None:
        self.dir = outdir / "submissions"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.fieldnames = fieldnames
        self.count = 0
        self.by_source: dict[str, int] = {}
        self.cpp_count = 0
        self.labelled_count = 0
        self.correct_count = 0
        self._jsonl = (self.dir / "submissions.jsonl").open(
            "w", encoding="utf-8", newline="\n"
        )
        self._csv = (self.dir / "submissions.csv").open(
            "w", encoding="utf-8-sig", newline=""
        )
        self._writer = csv.DictWriter(
            self._csv, fieldnames=fieldnames, extrasaction="ignore"
        )
        self._writer.writeheader()

    def add(self, row: dict[str, Any]) -> None:
        """Write one submission row and update the counters."""
        sync_aliases(row)
        self._jsonl.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._writer.writerow(flatten_for_csv(row))

        self.count += 1
        source = row.get("dataset_source") or "UNKNOWN"
        self.by_source[source] = self.by_source.get(source, 0) + 1
        if row.get("language") == "cpp":
            self.cpp_count += 1
        if row.get("label_status") == LABEL_SOURCE:
            self.labelled_count += 1
        if row.get("correct") is True:
            self.correct_count += 1

    def close(self) -> None:
        """Flush and close both files."""
        self._jsonl.close()
        self._csv.close()


def submission_fieldnames() -> list[str]:
    """Return the fixed column order for the submissions table."""
    fields = list(base_submission(
        source_dataset="X",
        source_submission_id="X",
        source_problem_id="X",
        run_id="X",
        provenance_ref="X",
        language="X",
    ).keys())
    fields.insert(fields.index("tracelearn_label"), "verdict_sequence_trace")
    return fields


# --------------------------------------------------------------------------
# adapter: PROGpedia
# --------------------------------------------------------------------------


def iter_progpedia(
    roots: list[Path], run_id: str, log: ExclusionLog, sink: "SubmissionsWriter"
) -> list[dict[str, Any]]:
    """Read PROGpedia problem statements and submissions."""
    problems: list[dict[str, Any]] = []
    seen: set[str] = set()

    for root in roots:
        if not root.exists():
            log.add("PROGPEDIA", str(root), "source", "source_not_downloaded", str(root))
            continue
        for prob_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            pid = prob_dir.name
            ref = rel_ref(prob_dir / "statement.md")
            stmt_path = prob_dir / "statement.md"
            if not stmt_path.exists():
                log.add("PROGPEDIA", pid, "problem", "missing_statement", ref)
                continue
            if pid in seen:
                log.add("PROGPEDIA", pid, "problem", "duplicate_source_problem_id", ref)
                continue

            try:
                text, encoding = read_text(stmt_path)
            except (OSError, TextDecodeError) as exc:
                log.add("PROGPEDIA", pid, "problem", "undecodable_file", str(exc))
                continue

            text = clean_text(text)
            if len(text) < 80:
                log.add("PROGPEDIA", pid, "problem", "empty_statement", ref)
                continue

            title, sections = split_markdown_sections(text)

            def body(*names: str) -> str | None:
                wanted = {n.lower() for n in names}
                for head, block in sections:
                    if head and head.strip().lower() in wanted and block:
                        return block
                return None

            inputs: list[str] = []
            outputs: list[str] = []
            for label, content in fenced_blocks(text):
                if label_is(label, "input"):
                    inputs.append(content)
                elif label_is(label, "output"):
                    outputs.append(content)

            example = body("example", "examples", "sample", "sample input") or text
            table = md_table_pairs(example)
            tests = build_sample_tests(inputs, outputs, table)

            record = base_problem(
                source_dataset="PROGPEDIA",
                source_problem_id=pid,
                run_id=run_id,
                provenance_ref=ref,
                source_sha256=sha256_bytes(stmt_path.read_bytes()),
                statement_format="markdown",
            )
            record["title"] = title or None
            record["statement_text"] = text
            record["input_description"] = nonempty(body("input", "input format") or "")
            record["output_description"] = nonempty(
                body("output", "output format") or ""
            )
            record["constraints"] = nonempty(
                body("constraints", "constraint", "limits") or ""
            )
            record["sample_tests"] = tests
            record["sample_test_count"] = len(tests)
            record["language_scope"] = "multi-language"
            record["source_encoding"] = encoding
            problems.append(record)
            seen.add(pid)

            for verdict_dir in sorted(p for p in prob_dir.iterdir() if p.is_dir()):
                verdict = verdict_dir.name
                for unit_dir in sorted(p for p in verdict_dir.iterdir() if p.is_dir()):
                    for src in sorted(unit_dir.rglob("*")):
                        if not src.is_file() or src.suffix.lower() not in CODE_EXTENSIONS:
                            continue
                        sref = rel_ref(src)
                        sdata = src.read_bytes()
                        if not sdata.strip():
                            log.add(
                                "PROGPEDIA",
                                sref,
                                "submission",
                                "empty_source_code",
                                sref,
                            )
                            continue
                        sub = base_submission(
                            source_dataset="PROGPEDIA",
                            source_submission_id=f"{pid}/{verdict}/{unit_dir.name}/{src.name}",
                            source_problem_id=pid,
                            run_id=run_id,
                            provenance_ref=sref,
                            language=CODE_EXTENSIONS[src.suffix.lower()],
                        )
                        sub["source_verdict"] = verdict
                        sub["source_verdict_definition"] = (
                            "source verdict directory name"
                        )
                        sub["source_code_sha256"] = sha256_bytes(sdata)
                        apply_outcome(sub, verdict)
                        if RUN_ARGS.inline_code:
                            sub["source_code"], _ = decode_bytes(sdata)
                        sink.add(sub)
    return problems


# --------------------------------------------------------------------------
# adapter: CodeStream
# --------------------------------------------------------------------------


def iter_codestream(
    root: Path, run_id: str, log: ExclusionLog, sink: "SubmissionsWriter"
) -> list[dict[str, Any]]:
    """Read CodeStream problems and submissions."""
    problems: list[dict[str, Any]] = []

    if not root.exists():
        log.add("CODESTREAM", str(root), "source", "source_not_downloaded", str(root))
        return problems

    problem_csv = root / "Problem Data.csv"
    raw = problem_csv.read_bytes()
    text, encoding = decode_bytes(raw)
    reader = csv.DictReader(io.StringIO(text, newline=""))

    for row in reader:
        pid = (row.get("problem_id") or "").strip()
        ref = rel_ref(problem_csv) + "#" + pid
        if not pid:
            log.add("CODESTREAM", ref, "problem", "missing_problem_id", ref)
            continue

        statement = clean_text(row.get("problem_description") or "")
        if len(statement) < 80:
            log.add("CODESTREAM", pid, "problem", "empty_statement", ref)
            continue

        title, sections = split_markdown_sections(statement)

        def body(*names: str) -> str | None:
            wanted = {n.lower() for n in names}
            for head, block in sections:
                if head and head.strip().lower().strip("#").strip() in wanted and block:
                    return block
            return None

        tests: list[dict[str, Any]] = []
        raw_cases = (row.get("evaluation_test_cases") or "").strip()
        if raw_cases:
            try:
                parsed = json.loads(raw_cases)
            except json.JSONDecodeError as exc:
                log.add("CODESTREAM", pid, "test_cases", "parse_error", str(exc))
                parsed = []
            for idx, case in enumerate(parsed, start=1):
                tests.append(
                    {
                        "test_index": case.get("test_case_no", idx),
                        "test_source": "evaluation_test_cases",
                        "input": str(case.get("input", "")),
                        "expected_output": str(case.get("output", "")),
                    }
                )
        if not tests:
            table = []
            for _head, block in sections:
                table.extend(md_table_pairs(block))
            tests = build_sample_tests([], [], table)

        if RUN_ARGS.exclude_without_tests and not tests:
            log.add("CODESTREAM", pid, "problem", "no_sample_tests", ref)
            continue

        record = base_problem(
            source_dataset="CODESTREAM",
            source_problem_id=pid,
            run_id=run_id,
            provenance_ref=ref,
            source_sha256=sha256_bytes(raw),
            statement_format="csv_markdown",
        )
        record["title"] = title or None
        record["statement_text"] = statement
        record["input_description"] = nonempty(
            strip_sample_block(body("input", "input format") or "")
        )
        record["output_description"] = nonempty(
            strip_sample_block(body("output", "output format") or "")
        )
        record["constraints"] = nonempty(body("constraints", "constraint", "limits") or "")
        record["sample_tests"] = tests
        record["sample_test_count"] = len(tests)
        record["language_scope"] = "c, c++, java"
        record["source_encoding"] = encoding
        problems.append(record)

    submission_csv = root / "Submission Data.csv"
    raw_sub = submission_csv.read_bytes()
    text_sub, encoding_sub = decode_bytes(raw_sub)
    for row in csv.DictReader(io.StringIO(text_sub, newline="")):
        sid = (row.get("submission_id") or "").strip()
        pid = (row.get("problem_id") or "").strip()
        ref = rel_ref(submission_csv) + "#" + sid
        if not sid or not pid:
            log.add("CODESTREAM", ref, "submission", "missing_source_id", ref)
            continue
        code = (row.get("source_code") or "").strip()
        if not code:
            log.add("CODESTREAM", sid, "submission", "empty_source_code", ref)
            continue

        lang_raw = (row.get("programming_language") or "").strip().lower()
        lang = "cpp" if lang_raw in {"c++", "cpp", "c++14", "c++17"} else lang_raw or "unknown"
        attempt = row.get("attempt_number") or ""
        sub = base_submission(
            source_dataset="CODESTREAM",
            source_submission_id=sid,
            source_problem_id=pid,
            run_id=run_id,
            provenance_ref=ref,
            language=lang,
        )
        sub["learner_id"] = (row.get("user_id") or "").strip() or None
        sub["attempt_number"] = int(attempt) if attempt.isdigit() else None
        sub["source_verdict"] = (row.get("final_verdict") or "").strip() or None
        sub["source_verdict_definition"] = "final evaluation result reported by source"
        sub["verdict_sequence_trace"] = (row.get("verdict_sequence_trace") or "").strip()
        sub["source_code_sha256"] = sha256_bytes(code.encode("utf-8"))
        apply_outcome(sub, sub["source_verdict"])
        if RUN_ARGS.inline_code:
            sub["source_code"] = code
        sink.add(sub)

    return problems


# --------------------------------------------------------------------------
# adapter: Project CodeNet
# --------------------------------------------------------------------------


def iter_codenet(
    root: Path, run_id: str, log: ExclusionLog, sink: "SubmissionsWriter"
) -> list[dict[str, Any]]:
    """Read CodeNet statements and C++ submissions."""
    problems: list[dict[str, Any]] = []

    if not root.exists():
        log.add("PROJECT_CODENET", str(root), "source", "source_not_downloaded", str(root))
        return problems

    desc_dir = root / "problem_descriptions"
    for html_path in sorted(desc_dir.glob("*.html")):
        pid = html_path.stem
        ref = rel_ref(html_path)
        try:
            raw_html = html_path.read_bytes()
            text, encoding = decode_bytes(raw_html)
        except (OSError, TextDecodeError) as exc:
            log.add("PROJECT_CODENET", pid, "problem", "undecodable_file", str(exc))
            continue

        parsed = parse_html_statement(text)
        statement = parsed["statement_text"]
        if len(statement) < 80:
            log.add("PROJECT_CODENET", pid, "problem", "empty_statement", ref)
            continue

        tests = parsed["sample_tests"]
        if RUN_ARGS.exclude_without_tests and not tests:
            log.add("PROJECT_CODENET", pid, "problem", "no_sample_tests", ref)
            continue

        record = base_problem(
            source_dataset="PROJECT_CODENET",
            source_problem_id=pid,
            run_id=run_id,
            provenance_ref=ref,
            source_sha256=sha256_bytes(raw_html),
            statement_format="html",
        )
        record["title"] = parsed["title"] or None
        record["statement_text"] = statement
        record["input_description"] = parsed["input_description"] or None
        record["output_description"] = parsed["output_description"] or None
        record["constraints"] = parsed["constraints"] or None
        record["sample_tests"] = tests
        record["sample_test_count"] = len(tests)
        record["language_scope"] = "multi-language"
        record["source_encoding"] = encoding
        record["section_headings"] = parsed["sections"]
        problems.append(record)

    # A problem is only usable if its statement was emitted above. Two
    # CodeNet problems (p02509, p02511) ship C++ submissions but no HTML
    # statement, so no problem row exists for them. Their submissions
    # would dangle, so record the emitted set and refuse orphans below.
    emitted_pids = {r["source_problem_id"] for r in problems}

    if not RUN_ARGS.with_submissions:
        return problems

    data_dir = root / "data"
    if not data_dir.exists():
        log.add("PROJECT_CODENET", str(data_dir), "submission", "missing_directory", str(data_dir))
        return problems

    # TraceLearn targets C++. This copy of CodeNet carries 53 language
    # directories, so the walk reads the C++ directory only.
    cpp_problems: dict[str, int] = {}
    global CODE_NET_CACHE
    CODE_NET_CACHE = HashCache(RUN_ARGS.hash_cache)
    cache = CODE_NET_CACHE
    limit = RUN_ARGS.limit

    for prob_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        pid = prob_dir.name
        cpp_dir = prob_dir / "C++"
        if not cpp_dir.is_dir():
            continue
        count = 0
        for src in sorted(cpp_dir.iterdir()):
            if not src.is_file():
                continue
            if src.suffix.lower() not in {".cpp", ".cc", ".cxx"}:
                continue
            if limit and sink.count >= limit:
                log.add(
                    "PROJECT_CODENET",
                    pid,
                    "submission",
                    "limit_reached",
                    f"limit={limit}",
                )
                cache.save()
                return problems
            sref = rel_ref(src)
            try:
                sdata = src.read_bytes()
            except OSError as exc:
                log.add("PROJECT_CODENET", sref, "submission", "read_error", str(exc))
                continue
            if not sdata.strip():
                log.add("PROJECT_CODENET", sref, "submission", "empty_source_code", sref)
                continue
            if pid not in emitted_pids:
                # The statement for this problem never parsed, so no
                # problem row exists. Emitting this submission would leave
                # a dangling problem_id link, so refuse it and log why.
                log.add(
                    "PROJECT_CODENET",
                    sref,
                    "submission",
                    "problem_not_ingested",
                    f"no parsed statement for {pid}",
                )
                continue
            sub = base_submission(
                source_dataset="PROJECT_CODENET",
                source_submission_id=f"{pid}/C++/{src.stem}",
                source_problem_id=pid,
                run_id=run_id,
                provenance_ref=sref,
                language="cpp",
            )
            sub["source_verdict"] = None
            sub["source_verdict_definition"] = (
                "not available: this copy has no metadata directory"
            )
            apply_outcome(sub, None)
            sub["source_code_sha256"] = cache.hash_file(src, sdata)
            if RUN_ARGS.inline_code:
                sub["source_code"], _ = decode_bytes(sdata)
            sink.add(sub)
            count += 1
        cpp_problems[pid] = count

    cache.save()

    # Mark which problems can back a student-facing problem set.
    for record in problems:
        have = cpp_problems.get(record["source_problem_id"], 0)
        record["cpp_submission_count"] = have
        record["has_reference_solutions"] = have > 0
        record["has_sample_tests"] = record["sample_test_count"] > 0
        record["student_ready"] = have > 0 and record["sample_test_count"] > 0

    return problems


# --------------------------------------------------------------------------
# sources the workspace does not hold
# --------------------------------------------------------------------------


MISSING_SOURCES = [
    ("MCMINING", "McMining / McMiner"),
    ("PROGFEED", "ProgFeed"),
    ("CSEDM2019", "CSEDM 2019 / ITAP"),
    ("HELP_DKT", "HELP-DKT"),
    ("FALCONCODE", "FalconCode"),
]


def log_absent_sources(log: ExclusionLog) -> None:
    """Log every planned source that this workspace does not hold."""
    for name, label in MISSING_SOURCES:
        log.add(name, label, "source", "source_not_downloaded", "no directory in workspace")


def log_internal_packs(log: ExclusionLog) -> None:
    """Log workspace folders that are not raw public sources."""
    for ref in (
        "TraceLearn_Dataset_Starter",
        "poc_data",
        "TraceLearn_Initial_Dataset_Summary.csv",
    ):
        if (RAW_ROOT / ref).exists() or (RAW_ROOT / ref).is_file():
            log.add("TRACELEARN_INTERNAL", ref, "source", "not_a_target_source", ref)


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------


@dataclass
class RunArgs:
    """Hold run wide flags read by the adapters."""

    inline_code: bool = False
    exclude_without_tests: bool = False
    with_submissions: bool = False
    limit: int = 0
    hash_cache: Path = DEFAULT_OUT / "hash_cache.json"


RUN_ARGS = RunArgs()
CODE_NET_CACHE: HashCache | None = None


def flatten_for_csv(row: dict[str, Any]) -> dict[str, Any]:
    """Return one record with nested values encoded as JSON strings."""
    flat: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (list, dict)):
            flat[key] = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            flat[key] = int(value)
        elif value is None:
            flat[key] = ""
        else:
            flat[key] = value
    return flat


def write_csv(path: Path, rows: list[dict[str, Any]]) -> int:
    """Write rows to one CSV file. Return the row count."""
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(flatten_for_csv(row))
    return len(rows)


def write_table(outdir: Path, name: str, rows: list[dict[str, Any]]) -> dict[str, int]:
    """Write one table as JSONL and CSV inside its own subfolder."""
    table_dir = outdir / name
    table_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        sync_aliases(row)
    jsonl_count = write_jsonl(table_dir / f"{name}.jsonl", rows)
    csv_count = write_csv(table_dir / f"{name}.csv", rows)
    return {"jsonl": jsonl_count, "csv": csv_count}


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    """Write rows to one JSONL file. Return the row count."""
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


# Master Plan section 5.1/5.2 name, Agent Brief section 5.1/5.2 name.
ALIAS_PAIRS = [
    ("dataset_source", "source_dataset"),
    ("source_record_id", "source_submission_id"),
    ("source_code_path", "source_code_ref"),
    ("statement", "statement_text"),
    ("input_spec", "input_description"),
    ("output_spec", "output_description"),
    ("label_status", "annotation_status"),
    ("tracelearn_label", "misconception_label"),
    ("timestamp", "submitted_at"),
    ("attempt_order", "attempt_number"),
]


def sync_aliases(row: dict[str, Any]) -> None:
    """Copy each alias field so both naming conventions agree.

    The first name in a pair is the Master Plan name. The second is the
    Agent Brief name. A non-null value on either side wins.
    """
    for master, brief in ALIAS_PAIRS:
        if master not in row and brief not in row:
            continue
        left = row.get(master)
        right = row.get(brief)
        value = left if left not in (None, "", [], 0) else right
        if value in (None, "", []):
            value = None
        if master in row:
            row[master] = value
        if brief in row:
            row[brief] = value


def write_readme(outdir: Path, manifest: dict[str, Any]) -> None:
    """Write one README.md per generated subfolder."""
    counts = manifest["counts"]
    run_id = manifest["ingestion_run_id"]
    parser = manifest["parser_version"]
    flags = manifest["flags"]

    common = (
        "Generated by `scripts/ingest_sources.py`.\n"
        "Do not edit these files by hand. Re-run the adapter instead.\n\n"
        f"- Ingestion run: `{run_id}`\n"
        f"- Parser version: `{parser}`\n"
        f"- Raw source: `{manifest['raw_root']}`\n"
        f"- Formats: JSONL and CSV\n"
    )

    root_readme = outdir / "README.md"
    root_readme.write_text(
        "# Normalized dataset tables\n\n" + common +
        "\n## Which file serves which TraceLearn product\n\n"
        "TraceLearn has two deliverables. Each normalized table feeds a different one.\n\n"
        "| Table | Student problem set | XGBoost misconception model |\n"
        "|---|---|---|\n"
        "| `problems/` | **Primary source.** Use `student_ready=true` rows to build the student-facing problem bank. | Context only. Supplies problem text and tests as features. Not a training target. |\n"
        "| `submissions/` | Reference solutions only. Use `correct=true` C++ rows as clean exemplars. | **Primary feature source.** Code, verdicts and outcomes feed feature extraction. Labels are still empty. |\n"
        "| `exclusions/` | No. Audit trail only. | No. Audit trail only. |\n\n"
        "### Read this before you build the XGBoost set\n\n"
        "`submissions/` gives you **features but no misconception targets**. No local source carries a\n"
        "CPP-M01 to CPP-M08 label. `tracelearn_label` is null in every row. Human annotation must run\n"
        "before any supervised training. Do not treat a source verdict as a misconception label.\n\n"
        "### Read this before you build the student set\n\n"
        "Filter `problems/` on `student_ready=true` to get problems that have both a statement with\n"
        "sample tests and at least one C++ reference solution. PROGpedia and CodeStream rows do not\n"
        "set `student_ready`; filter them on `sample_test_count>0` plus a matching `submissions/` row.\n\n"
        "## Tables\n\n"
        "| Folder | Rows | Purpose |\n|---|---:|---|\n"
        f"| `problems/` | {counts['problems']} | One row per programming problem statement. |\n"
        f"| `submissions/` | {counts['submissions']} | One row per source submission. |\n"
        f"| `exclusions/` | {counts['exclusions']} | One row per record the adapter refused. |\n"
        "\n## Source counts\n\n"
        "| Source | Problems | Submissions |\n|---|---:|---:|\n"
        + "".join(
            f"| {src} | {counts['problems_by_source'].get(src, 0)} "
            f"| {counts['submissions_by_source'].get(src, 0)} |\n"
            for src in sorted(
                set(counts["problems_by_source"]) | set(counts["submissions_by_source"])
            )
        )
        + "\n## Flags used\n\n"
        + "".join(f"- `{k}`: `{v}`\n" for k, v in sorted(flags.items()))
        + "\n## File map\n\n"
        "- `ingest_run_manifest.json` — machine-readable run summary.\n"
        "- `hash_cache.json` — SHA-256 cache for the CodeNet C++ walk.\n"
        "- `README.md` — this file.\n",
        encoding="utf-8",
    )

    (outdir / "problems" / "README.md").write_text(
        "# problems\n\n" + common +
        f"\nRows: **{counts['problems']}**\n\n"
        "One row per programming problem statement parsed from a raw source.\n\n"
        "## TraceLearn purpose\n\n"
        "**This table feeds the student problem set.**\n\n"
        "It is the only table that holds a human-readable statement. Build the student-facing\n"
        "problem bank from these rows. Filter on `student_ready=true` to keep problems that have\n"
        "both sample tests and at least one C++ reference solution.\n\n"
        "| Product | How to use this table |\n|---|---|\n"
        "| Student problem set | **Primary source.** Filter `student_ready=true`. |\n"
        "| XGBoost model | Context features only. `statement_text`, `concept_tags` and `difficulty` can become predictors. This table is never a training target. |\n\n"
        "## Files\n\n"
        "- `problems.jsonl` — one JSON object per line. Canonical format.\n"
        "- `problems.csv` — same rows. Lists and objects are JSON strings. UTF-8 with BOM.\n\n"
        "## Field groups\n\n"
        "| Group | Fields |\n|---|---|\n"
        "| Identity | `problem_id`, `dataset_source`, `source_dataset`, `source_problem_id` |\n"
        "| Statement | `title`, `statement` / `statement_text`, `input_spec`, `output_spec`, `constraints` |\n"
        "| Tests | `sample_tests`, `sample_test_count` |\n"
        "| Scope | `language_scope`, `statement_format`, `concept_tags`, `difficulty` |\n"
        "| Provenance | `provenance_id`, `provenance_ref`, `source_sha256`, `source_encoding` |\n"
        "| CodeNet readiness | `cpp_submission_count`, `has_reference_solutions`, `has_sample_tests`, `student_ready` |\n\n"
        "## Naming convention\n\n"
        "Every row carries two names for the same value.\n\n"
        "| Master Plan field | Agent Brief field |\n|---|---|\n"
        "| `dataset_source` | `source_dataset` |\n"
        "| `statement` | `statement_text` |\n"
        "| `input_spec` | `input_description` |\n"
        "| `output_spec` | `output_description` |\n\n"
        "`problem_id` is stable across runs. It has the form `tl-<source>-<source_problem_id>`.\n\n"
        "## Rules\n\n"
        "1. Keep source-native text. Do not rewrite statements.\n"
        "2. `sample_tests` holds statement sample cases only. It is not a full test suite.\n"
        "3. `student_ready` is true when a problem has both C++ code and sample tests.\n"
        "4. Review each statement with a teacher before students see it.\n",
        encoding="utf-8",
    )

    (outdir / "submissions" / "README.md").write_text(
        "# submissions\n\n" + common +
        f"\nRows: **{counts['submissions']}**\n\n"
        "One row per source submission record.\n\n"
        "## TraceLearn purpose\n\n"
        "**This table feeds the XGBoost misconception model.**\n\n"
        "It is the only table that holds code and outcomes per attempt. Feature extraction reads\n"
        "these rows. The student problem set uses only the `correct=true` C++ rows as reference\n"
        "solutions.\n\n"
        "| Product | How to use this table |\n|---|---|\n"
        "| XGBoost model | **Primary feature source.** Read `source_code_path`, `source_code_sha256`, `compile_status`, `runtime_status` and `correct`. |\n"
        "| Student problem set | Reference solutions only. Filter `language=cpp` and `correct=true`. |\n\n"
        "**Blocking gap.** `tracelearn_label` is null in every row. Features exist. Misconception\n"
        "targets do not. Human annotation must run before supervised training.\n\n"
        "## Files\n\n"
        "- `submissions.jsonl` — one JSON object per line. Canonical format.\n"
        "- `submissions.csv` — same rows. `source_code` stays null unless `--inline-code`.\n\n"
        "## Field groups\n\n"
        "| Group | Fields |\n|---|---|\n"
        "| Identity | `submission_id`, `source_record_id`, `dataset_source`, `problem_id` |\n"
        "| Learner | `learner_id`, `source_learner_id`, `attempt_order`, `timestamp` |\n"
        "| Code | `language`, `source_code_path`, `source_code_sha256`, `source_code` |\n"
        "| Outcome | `source_verdict`, `compile_status`, `runtime_status`, `correct` |\n"
        "| Label | `label_status`, `tracelearn_label`, `label_confidence` |\n"
        "| Provenance | `provenance_id`, `provenance_ref`, `ingestion_run_id` |\n\n"
        "## Naming convention\n\n"
        "| Master Plan field | Agent Brief field |\n|---|---|\n"
        "| `dataset_source` | `source_dataset` |\n"
        "| `source_record_id` | `source_submission_id` |\n"
        "| `source_code_path` | `source_code_ref` |\n"
        "| `attempt_order` | `attempt_number` |\n"
        "| `timestamp` | `submitted_at` |\n"
        "| `label_status` | `annotation_status` |\n"
        "| `tracelearn_label` | `misconception_label` |\n\n"
        "## Rules\n\n"
        "1. `tracelearn_label` is null in every row. No source supplies misconception labels.\n"
        "2. `label_status` is `source_label` only when the source gave a verdict.\n"
        "3. `correct` follows the source verdict only. It is not a TraceLearn judgement.\n"
        "4. Code stays in the raw tree. `source_code_path` points at it. Never rewrite it.\n"
        "5. Do not convert a source verdict into a misconception label.\n\n"
        "## Known gaps\n\n"
        "- Project CodeNet rows have no verdict. This copy has no `metadata/` directory.\n"
        "- PROGpedia rows carry a verdict directory name only. There is no per-test result.\n",
        encoding="utf-8",
    )

    (outdir / "exclusions" / "README.md").write_text(
        "# exclusions\n\n" + common +
        f"\nRows: **{counts['exclusions']}**\n\n"
        "One row per record the adapter refused to write. Nothing is deleted silently.\n\n"
        "## TraceLearn purpose\n\n"
        "**Neither product reads this table.** It is a quality audit trail.\n\n"
        "| Product | Use |\n|---|---|\n"
        "| Student problem set | No use. |\n"
        "| XGBoost model | No use. |\n\n"
        "Use this table to prove completeness. Every count in a report must reconcile against it.\n\n"
        "## Files\n\n"
        "- `exclusions.jsonl` — one JSON object per line.\n"
        "- `exclusions.csv` — same rows.\n\n"
        "## Fields\n\n"
        "| Field | Meaning |\n|---|---|\n"
        "| `run_id` | The ingestion run that refused the record. |\n"
        "| `source_dataset` | Source that owned the record. |\n"
        "| `record_ref` | Source-native identifier of the record. |\n"
        "| `stage` | `source`, `problem`, `submission` or `test_cases`. |\n"
        "| `exclusion_reason` | Machine-readable reason code. |\n"
        "| `detail` | Human-readable context. |\n\n"
        "## Reason codes in this run\n\n"
        "| Reason | Count |\n|---|---:|\n"
        + "".join(
            f"| `{reason}` | {n} |\n"
            for reason, n in sorted(manifest["exclusions_by_reason"].items())
        )
        + "\n## Reason code meanings\n\n"
        "| Reason | Meaning |\n|---|---|\n"
        "| `source_not_downloaded` | The planned dataset is absent from this workspace. |\n"
        "| `not_a_target_source` | The folder is internal, not a public raw source. |\n"
        "| `missing_statement` | The problem folder has no `statement.md`. |\n"
        "| `empty_statement` | The statement parsed to fewer than 80 characters. |\n"
        "| `undecodable_file` | No supported character encoding matched. |\n"
        "| `empty_source_code` | The submission file holds no code bytes. |\n"
        "| `no_sample_tests` | The problem has no sample tests. Only logged with `--exclude-without-tests`. |\n"
        "| `duplicate_source_problem_id` | The source problem id was already ingested. |\n"
        "| `problem_not_ingested` | The submission's parent problem has no parsed statement, so no problem row exists. |\n"
        "| `limit_reached` | `--limit` stopped the walk. |\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    """Run the adapter and write the normalized outputs."""
    ap = argparse.ArgumentParser(description="TraceLearn source ingestion adapter.")
    ap.add_argument(
        "--sources",
        default="all",
        help="Comma list: codenet,codestream,progpedia or all",
    )
    ap.add_argument("--outdir", default=str(DEFAULT_OUT), help="Output directory")
    ap.add_argument(
        "--hash-cache",
        default=str(DEFAULT_OUT / "hash_cache.json"),
        help="SHA-256 cache file for the CodeNet C++ walk",
    )
    ap.add_argument("--inline-code", action="store_true", help="Store code inside records")
    ap.add_argument(
        "--with-submissions",
        action="store_true",
        help=(
            "Walk the Project CodeNet source tree and emit submission records. "
            "PROGpedia and CodeStream submissions always emit; they are small."
        ),
    )
    ap.add_argument("--limit", type=int, default=0, help="Max submissions per source")
    ap.add_argument(
        "--exclude-without-tests",
        action="store_true",
        help="Drop problems that have no sample tests",
    )
    ap.add_argument(
        "--raw-root",
        default=str(RAW_ROOT),
        help="Path to Datasets_RAW directory (overrides compiled-in default)",
    )
    args = ap.parse_args(argv)

    global RAW_ROOT
    RAW_ROOT = Path(args.raw_root)

    RUN_ARGS.inline_code = args.inline_code
    RUN_ARGS.exclude_without_tests = args.exclude_without_tests
    RUN_ARGS.with_submissions = args.with_submissions
    RUN_ARGS.limit = args.limit
    RUN_ARGS.hash_cache = Path(args.hash_cache)

    started = datetime.now(timezone.utc)
    run_id = f"run-{started.strftime('%Y%m%dT%H%M%SZ')}-{os.urandom(4).hex()}"
    log = ExclusionLog(run_id=run_id)

    wanted = {s.strip().lower() for s in args.sources.split(",") if s.strip()}
    if "all" in wanted:
        wanted = {"codenet", "codestream", "progpedia"}

    problems: list[dict[str, Any]] = []

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    sink = SubmissionsWriter(outdir, submission_fieldnames())

    if "progpedia" in wanted:
        problems.extend(
            iter_progpedia(
                [RAW_ROOT / "progpedia", RAW_ROOT / "progpedia (1)"], run_id, log, sink
            )
        )
    if "codestream" in wanted:
        problems.extend(
            iter_codestream(
                RAW_ROOT / "CodeStream A Dataset of Iterative Programming Subm",
                run_id,
                log,
                sink,
            )
        )
    if "codenet" in wanted:
        problems.extend(
            iter_codenet(
                RAW_ROOT / "Project_CodeNet" / "Project_CodeNet", run_id, log, sink
            )
        )

    sink.close()

    log_absent_sources(log)
    log_internal_packs(log)

    counts = {
        "problems": write_table(outdir, "problems", problems),
        "submissions": {"jsonl": sink.count, "csv": sink.count},
        "exclusions": write_table(outdir, "exclusions", log.rows),
    }

    per_source: dict[str, int] = {}
    for row in problems:
        per_source[row["dataset_source"]] = per_source.get(row["dataset_source"], 0) + 1

    per_source_sub = sink.by_source

    tested = sum(1 for row in problems if row["sample_test_count"] > 0)
    total_tests = sum(row["sample_test_count"] for row in problems)
    cpp_subs = sink.cpp_count
    labelled = sink.labelled_count
    correct = sink.correct_count

    cache_hits = ""
    if isinstance(CODE_NET_CACHE, HashCache):
        cache_hits = f"{CODE_NET_CACHE.hits} cached, {CODE_NET_CACHE.misses} hashed"

    manifest = {
        "ingestion_run_id": run_id,
        "parser_version": PARSER_VERSION,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "raw_root": str(RAW_ROOT),
        "output_dir": str(outdir),
        "flags": {
            "sources": sorted(wanted),
            "inline_code": args.inline_code,
            "with_submissions": args.with_submissions,
            "limit": args.limit,
            "exclude_without_tests": args.exclude_without_tests,
        },
        "formats": ["jsonl", "csv"],
        "counts": {
            "problems": counts["problems"]["jsonl"],
            "submissions": counts["submissions"]["jsonl"],
            "exclusions": counts["exclusions"]["jsonl"],
            "problems_by_source": per_source,
            "submissions_by_source": per_source_sub,
            "problems_with_sample_tests": tested,
            "sample_tests_total": total_tests,
            "cpp_submissions": cpp_subs,
            "submissions_with_source_label": labelled,
            "submissions_marked_correct": correct,
        },
        "code_net_hash_cache": cache_hits,
        "exclusions_by_reason": log.count_by_reason(),
    }
    (outdir / "ingest_run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    write_readme(outdir, manifest)

    print(json.dumps(manifest["counts"], indent=2, ensure_ascii=False))
    print("exclusions by reason:", json.dumps(manifest["exclusions_by_reason"], indent=2))
    print("manifest:", outdir / "ingest_run_manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
