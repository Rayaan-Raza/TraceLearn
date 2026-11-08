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
