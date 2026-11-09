"""Produce one submission's run record. Runs inside the backend's sandbox: no network, no app files.

Reads {"code", "lang", "tests"} on stdin and writes the record as JSON on stdout. It calls the same
functions that built the training data (`counterfactual_evidence`), so a served feature is measured
the way the model saw it in training. Student programs run with their output sent to files, so their
prints cannot reach this process's stdout. They do share its sandbox, so a hostile program could
tamper with its own record: this can mislead that student's own diagnosis and nothing else.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    sys.path.insert(0, str(p))

os.environ["SANDBOX_RUNNER_ALREADY_CONFINED"] = "1"  # see sandbox_runner/process.py

import counterfactual_evidence as C  # noqa: E402


def main() -> int:
    job = json.load(sys.stdin)
    job.setdefault("row_id", "live")
    json.dump(C.evidence_for(job), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
