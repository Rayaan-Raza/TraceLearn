"""Inference-time feature builder (B1).

Bridges `tracelearn_features.extractor` and the live backend: compiles the
compile stderr, test runner output and optional problem context into the flat
`{block.feature: value}` mapping `ModelClassifier.predict()` expects.

Runtime tools (ASan / UBSan / Valgrind) are not available at inference time,
so the runtime block is intentionally left as NaN throughout.
"""
from __future__ import annotations

import re
from typing import Any

from tracelearn_features.cpg_source import extract_cpg_source
from tracelearn_features.extractor import extract_features

# Matches [-Wsome-flag] or [-Wsome=value] at the end of a g++ warning line.
_WFLAG_RE = re.compile(r"\[-W([^\]]+)\]")


def parse_warnings(compile_stderr: str) -> list[dict[str, Any]]:
    """Parse g++ stderr into the warnings evidence list.

    Returns one ``{"flag": "-W...", "count": N}`` entry per distinct flag, in
    the order first seen.  Lines that are not warnings (errors, notes) are
    silently ignored.
    """
    counts: dict[str, int] = {}
    order: list[str] = []
    for line in compile_stderr.splitlines():
        if ": warning:" not in line:
            continue
        m = _WFLAG_RE.search(line)
        if not m:
            continue
        flag = f"-W{m.group(1)}"
        if flag not in counts:
            order.append(flag)
            counts[flag] = 0
        counts[flag] += 1
    return [{"flag": f, "count": counts[f]} for f in order]


def map_test_results(test_case_results: list[Any]) -> dict[str, Any] | None:
    """Convert a list of ``TestCaseResult`` objects to the tests evidence dict.

    Returns ``None`` when the list is empty so the caller can leave the tests
    block as NaN rather than fabricating zeros.
    """
    if not test_case_results:
        return None

    items: list[dict[str, Any]] = []
    for r in test_case_results:
        ok = bool(getattr(r, "passed", False))
        err = getattr(r, "error_type", None) or ""
        if err == "Timeout":
            kind = "timeout"
        elif err in ("RuntimeError", "MemoryLimitExceeded", "OutputLimitExceeded"):
            kind = "crash"
        else:
            kind = "wrong_answer"
        entry: dict[str, Any] = {"ok": ok, "kind": kind, "boundary": False}
        expected = getattr(r, "expected_output", None)
        actual = getattr(r, "actual_output", None)
        if expected is not None:
            entry["expected"] = expected
        if actual is not None:
            entry["actual"] = actual
        items.append(entry)

    return {"results": items}


class InferenceFeatureBuilder:
    """Build a flat feature dict from live backend data for model inference.

    Example::

        builder = InferenceFeatureBuilder()
        flat = builder.build(
            source=submission.source_code,
            compile_stderr=compile_err.stderr,   # from compile_cpp()
            test_results=exec_result.test_results,  # from run_submission_tests()
            context={"statement_length": len(problem.description)},
        )
        prediction = model.predict(flat)
    """

    def build(
        self,
        source: str,
        compile_stderr: str = "",
        test_results: list[Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a flat ``{block.feature: value}`` dict for the classifier."""
        warnings_ev = parse_warnings(compile_stderr) if compile_stderr else None
        tests_ev = map_test_results(test_results) if test_results else None

        cpg_ev: dict[str, Any] | None = None
        if source and source.strip():
            cpg_ev = extract_cpg_source(source) or None

        blocks = extract_features(
            source,
            language="cpp",
            warnings=warnings_ev,
            tests=tests_ev,
            cpg=cpg_ev,
            context=context,
            # runtime omitted — not available at inference time
        )

        flat: dict[str, Any] = {}
        for block_name, block_feats in blocks.items():
            for short, value in block_feats.items():
                flat[f"{block_name}.{short}"] = value
        return flat
