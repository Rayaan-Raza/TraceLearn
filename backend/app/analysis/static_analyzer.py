from __future__ import annotations
import ast
from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.diagnosis.taxonomy import M01_LOOP_BOUNDARY, M02_INDEX_VALUE, M03_MISSING_RETURN

class StaticAnalyzer:
    def analyze(self, source_code: str, function_name: str) -> list[EvidenceRecord]:
        items: list[EvidenceRecord] = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return items
        items.extend(self._detect_m01(tree))
        items.extend(self._detect_m02(tree))
        items.extend(self._detect_m03(tree, function_name))
        return items

    def _detect_m01(self, tree: ast.AST) -> list[EvidenceRecord]:
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
                if len(node.args) >= 1:
                    arg = node.args[-1]
                    if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add):
                        if isinstance(arg.left, ast.Name) or isinstance(arg.left, ast.Constant):
                            if isinstance(arg.right, ast.Constant) and arg.right.value == 1:
                                found = True
        if found:
            return [EvidenceRecord(
                source_type="static", evidence_code="STATIC_RANGE_N_PLUS_ONE",
                misconception_id=M01_LOOP_BOUNDARY, direction="support", weight=0.0,
                description="range upper bound uses n + 1",
            )]
        return []

    def _detect_m02(self, tree: ast.AST) -> list[EvidenceRecord]:
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                target_names = []
                if isinstance(node.target, ast.Name):
                    target_names.append(node.target.id)
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Subscript) and isinstance(inner.slice, ast.Name):
                        if inner.slice.id in target_names:
                            return [EvidenceRecord(
                                source_type="static", evidence_code="STATIC_ITER_VALUE_USED_AS_INDEX",
                                misconception_id=M02_INDEX_VALUE, direction="support", weight=0.0,
                                description="loop variable used as collection index",
                            )]
        return []

    def _detect_m03(self, tree: ast.AST, function_name: str) -> list[EvidenceRecord]:
        items: list[EvidenceRecord] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                has_return = any(isinstance(n, ast.Return) and n.value is not None for n in ast.walk(node))
                has_print = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print" for n in ast.walk(node))
                if has_print:
                    items.append(EvidenceRecord(
                        source_type="static", evidence_code="STATIC_PRINT_INSTEAD_OF_RETURN",
                        misconception_id=M03_MISSING_RETURN, direction="support", weight=0.0,
                        description="print() used where return expected",
                    ))
                if not has_return:
                    items.append(EvidenceRecord(
                        source_type="static", evidence_code="STATIC_NO_RETURN",
                        misconception_id=M03_MISSING_RETURN, direction="support", weight=0.0,
                        description="function lacks return statement",
                    ))
        return items
