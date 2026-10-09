"""Static analysis for C++ source code using pattern matching and g++ diagnostics."""
from __future__ import annotations
import re
import subprocess
import tempfile
from pathlib import Path
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.diagnosis.taxonomy import (
    CPP_LOOP_BOUNDARY, CPP_ARRAY_BOUNDS, CPP_UNINITIALIZED_VAR,
    CPP_INT_OVERFLOW, CPP_MISSING_BASE_CASE, CPP_ASSIGN_VS_COMPARE,
    CPP_WRONG_LOOP_DIR, CPP_OFF_BY_ONE,
)


class CppStaticAnalyzer:
    def analyze(self, source_code: str, function_name: str = "") -> list[EvidenceRecord]:
        items: list[EvidenceRecord] = []
        items.extend(self._detect_assign_vs_compare(source_code))
        items.extend(self._detect_loop_boundary(source_code))
        items.extend(self._detect_off_by_one(source_code))
        items.extend(self._detect_uninitialized_patterns(source_code))
        items.extend(self._detect_int_overflow_risk(source_code))
        items.extend(self._detect_missing_base_case(source_code))
        items.extend(self._parse_compiler_warnings(source_code))
        return items

    def _detect_assign_vs_compare(self, src: str) -> list[EvidenceRecord]:
        # Assignment inside if/while condition: if (x = y)
        pattern = re.compile(r'\b(if|while)\s*\([^)]*(?<!=)=(?!=)[^)]*\)')
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
        items: list[EvidenceRecord] = []
        with tempfile.TemporaryDirectory() as tmp:
            src_path = Path(tmp) / "check.cpp"
            src_path.write_text(src, encoding="utf-8")
            try:
                result = subprocess.run(
                    ["g++", "-std=c++17", "-Wall", "-Wextra", "-fsyntax-only", str(src_path)],
                    capture_output=True, text=True, timeout=10,
                )
                stderr = result.stderr
            except Exception:
                return items

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
