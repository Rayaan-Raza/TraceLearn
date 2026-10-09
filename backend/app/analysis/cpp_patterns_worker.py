"""Subprocess entry point: run C++ pattern detectors on stdin, print JSON.

Invoked by CppStaticAnalyzer with a hard timeout (see _PatternWorker).
"""
import dataclasses
import json
import sys

from backend.app.analysis.cpp_static import _run_pattern_detectors

if __name__ == "__main__":
    records = _run_pattern_detectors(sys.stdin.read())
    json.dump([dataclasses.asdict(r) for r in records], sys.stdout)
