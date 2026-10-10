"""Static analysis for C++ source code using pattern matching and g++ diagnostics."""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.diagnosis.taxonomy import (
    CPP_LOOP_BOUNDARY, CPP_ARRAY_BOUNDS, CPP_UNINITIALIZED_VAR,
    CPP_INT_OVERFLOW, CPP_MISSING_BASE_CASE, CPP_ASSIGN_VS_COMPARE,
    CPP_WRONG_LOOP_DIR, CPP_OFF_BY_ONE,
)


REGEX_TIME_BUDGET_SECONDS = 3.0
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _run_pattern_detectors(source_code: str) -> list[EvidenceRecord]:
    """Module-level so it can run in a worker process (see _PatternWorker)."""
    a = CppStaticAnalyzer()
    items: list[EvidenceRecord] = []
    items.extend(a._detect_assign_vs_compare(source_code))
    items.extend(a._detect_loop_boundary(source_code))
    items.extend(a._detect_off_by_one(source_code))
    items.extend(a._detect_uninitialized_patterns(source_code))
    items.extend(a._detect_int_overflow_risk(source_code))
    items.extend(a._detect_missing_base_case(source_code))
    return items


class _PatternWorker:
    """Runs the regex detectors in a separate process with a time budget.

    Several detectors use backtracking regexes whose cost grows polynomially
    on adversarial input; Python's re module has no timeout, so a crafted
    submission could otherwise pin a server thread. On timeout the worker is
    killed and no pattern evidence is produced for that submission.
    """

    def run(self, source_code: str) -> list[EvidenceRecord]:
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "backend.app.analysis.cpp_patterns_worker"],
                input=source_code, capture_output=True, text=True,
                timeout=REGEX_TIME_BUDGET_SECONDS, cwd=str(_PROJECT_ROOT),
                env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(_PROJECT_ROOT), "PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.TimeoutExpired:
            return []
        if proc.returncode != 0:
            return []
        try:
            return [EvidenceRecord(**row) for row in json.loads(proc.stdout)]
        except (ValueError, TypeError):
            return []


_pattern_worker = _PatternWorker()


class CppStaticAnalyzer:
    def analyze(self, source_code: str, function_name: str = "") -> list[EvidenceRecord]:
        items: list[EvidenceRecord] = []
        items.extend(_pattern_worker.run(source_code))
        items.extend(self._parse_compiler_warnings(source_code))
        return items

    def _detect_assign_vs_compare(self, src: str) -> list[EvidenceRecord]:
        # Assignment inside if/while condition: if (x = y). The `=` of `<=`,
        # `>=`, `!=`, `==` and of compound operators is not an assignment test.
        pattern = re.compile(r'\b(if|while)\s*\([^)]*(?<![=!<>+\-*/%&|^])=(?!=)[^)]*\)')
        if pattern.search(src):
            return [EvidenceRecord(
                source_type="static", evidence_code="CPP_ASSIGN_IN_CONDITION",
                misconception_id=CPP_ASSIGN_VS_COMPARE, direction="support", weight=0.0,
                description="Assignment (=) used inside condition — likely meant comparison (==)",
            )]
        return []

    def _detect_loop_boundary(self, src: str) -> list[EvidenceRecord]:
        # for (int i = 0; i <= n; i++) — off-by-one via <= with array size
        pattern = re.compile(r'for\s*\([^;]*;\s*\w+\s*<=\s*\w+\s*;')
        if pattern.search(src):
            return [EvidenceRecord(
                source_type="static", evidence_code="CPP_LOOP_LE_BOUND",
                misconception_id=CPP_LOOP_BOUNDARY, direction="support", weight=0.0,
                description="Loop uses <= with upper bound — possible off-by-one error",
            )]
        return []

    def _detect_off_by_one(self, src: str) -> list[EvidenceRecord]:
        # Array access with exact size: arr[n] where n is likely the size
        pattern = re.compile(r'\[\s*n\s*\]|\[\s*size\s*\]|\[\s*len\s*\]')
        if pattern.search(src):
            return [EvidenceRecord(
                source_type="static", evidence_code="CPP_ARRAY_AT_SIZE",
                misconception_id=CPP_OFF_BY_ONE, direction="support", weight=0.0,
                description="Array indexed at exact size variable — likely off-by-one",
            )]
        return []

    def _detect_uninitialized_patterns(self, src: str) -> list[EvidenceRecord]:
        # Declared without initializer and used in arithmetic: int x; x += ...
        pattern = re.compile(r'\bint\s+(\w+)\s*;.*?\1\s*[+\-\*\/]?=', re.DOTALL)
        if pattern.search(src):
            return [EvidenceRecord(
                source_type="static", evidence_code="CPP_UNINIT_VAR",
                misconception_id=CPP_UNINITIALIZED_VAR, direction="support", weight=0.0,
                description="Variable declared without initializer then used in accumulation",
            )]
        return []

    def _detect_int_overflow_risk(self, src: str) -> list[EvidenceRecord]:
        # int used but multiplied or summed in ways that suggest long long needed
        if re.search(r'\bint\b.*\*.*\bint\b', src) or re.search(r'1e[89]|1000000000', src):
            return [EvidenceRecord(
                source_type="static", evidence_code="CPP_INT_OVERFLOW_RISK",
                misconception_id=CPP_INT_OVERFLOW, direction="support", weight=0.0,
                description="int used in context suggesting possible 32-bit overflow",
            )]
        return []

    def _detect_missing_base_case(self, src: str) -> list[EvidenceRecord]:
        # Recursive function without an early return before the recursive call
        if not re.search(r'\b\w+\s*\([^)]*\)\s*\{[^}]*\breturn\b[^}]*\b\w+\s*\(', src, re.DOTALL):
            return []
        # Rough check: function calls itself and has no if-return before the call
        fn_match = re.search(r'(\w+)\s*\([^)]*\)\s*\{', src)
        if not fn_match:
            return []
        fn_name = fn_match.group(1)
        if fn_name in ("main", "int", "void"):
            return []
        body_match = re.search(r'\{(.+)\}', src, re.DOTALL)
        if not body_match:
            return []
        body = body_match.group(1)
        # If there's a recursive call but no if-return before it
        has_recurse = re.search(rf'\b{re.escape(fn_name)}\s*\(', body)
        has_base = re.search(r'\bif\b[^{]*\breturn\b', body)
        if has_recurse and not has_base:
            return [EvidenceRecord(
                source_type="static", evidence_code="CPP_MISSING_BASE_CASE",
                misconception_id=CPP_MISSING_BASE_CASE, direction="support", weight=0.0,
                description="Recursive function appears to lack a base case return",
            )]
        return []

    def _parse_compiler_warnings(self, src: str) -> list[EvidenceRecord]:
        # Runs g++ on untrusted code, so it goes through the same sandbox as
        # execution. Output is only pattern-matched, never returned to users.
        from backend.app.execution.sandbox import check_cpp_source, new_workdir, run_in_sandbox

        items: list[EvidenceRecord] = []
        if check_cpp_source(src):
            return items
        tmp = new_workdir()
        try:
            Path(tmp.name, "check.cpp").write_text(src, encoding="utf-8")
            result = run_in_sandbox(
                ["g++", "-std=c++17", "-Wall", "-Wextra", "-fsyntax-only", "check.cpp"],
                Path(tmp.name), timeout=10, memory_mb=2048,
            )
            stderr = result.stderr
        except Exception:
            return items
        finally:
            tmp.cleanup()

        warn_map = [
            (r"uninitialized", CPP_UNINITIALIZED_VAR, "CPP_GCC_UNINIT", "g++ warns: uninitialized variable"),
            (r"suggest parentheses|= instead of ==", CPP_ASSIGN_VS_COMPARE, "CPP_GCC_ASSIGN", "g++ warns: possible assignment in condition"),
            (r"array subscript|out of bounds", CPP_ARRAY_BOUNDS, "CPP_GCC_BOUNDS", "g++ warns: array bounds issue"),
            (r"integer overflow", CPP_INT_OVERFLOW, "CPP_GCC_OVERFLOW", "g++ warns: integer overflow"),
        ]
        for pattern, misc_id, code, desc in warn_map:
            if re.search(pattern, stderr, re.IGNORECASE):
                items.append(EvidenceRecord(
                    source_type="static", evidence_code=code,
                    misconception_id=misc_id, direction="support", weight=0.0,
                    description=desc,
                ))
        return items
