"""Run the trained misconception classifier on one submission and return evidence.

Safety rules (this is the path a student's code takes into a diagnosis):

- `settings.model_diagnosis == "off"`: nothing is loaded, nothing runs.
- Any failure (missing files, a contract error, a feature error, an oversized
  source) returns no evidence and logs; it never raises into the pipeline, so the rule
  engine always still produces a diagnosis.
- `shadow`: the prediction is stored as neutral, weightless evidence
  (`MODEL_SHADOW`) so it can be audited against teacher decisions; the diagnosis
  does not change.
- `on`: the prediction becomes `MODEL_PREDICTION` / `MODEL_ABSTAINED` /
  `MODEL_OTHER_ERROR` (see `model_evidence`). If too many features are missing
  (compiler-warning counts come from compiling the submission with the training flags;
  when that fails the block is absent) the prediction is forced to abstain, because a
  model fed inputs it was not trained on is not trustworthy.
"""
from __future__ import annotations

import dataclasses
import logging
import math
from functools import lru_cache
from typing import Any

from backend.app.analysis.evidence_models import EvidenceRecord
from backend.app.analysis.model_evidence import model_evidence
from backend.app.config import settings
from backend.app.diagnosis.xgb_classifier import ModelClassifier, ModelPrediction, repair_override

log = logging.getLogger(__name__)

MAX_SOURCE_CHARS = 20_000
# The flags the training data's warning counts were produced with (sandbox_runner/config.py WARNING_FLAGS);
# copied so the backend does not import the research package.
WARNING_FLAGS = ["-O2", "-Wall", "-Wextra", "-Wmaybe-uninitialized", "-Wparentheses", "-Warray-bounds", "-Wshadow",
                 "-Wconversion", "-fdiagnostics-color=never", "-fno-diagnostics-show-caret"]
# Share of the model's features that may be missing before "on" abstains.
MAX_MISSING_SHARE = 0.25


@lru_cache(maxsize=2)
def _classifier(variant: str, models_dir: str) -> ModelClassifier:
    return ModelClassifier.load(variant, models_dir)


def code_features(source: str, language: str = "cpp", warnings: dict[str, Any] | None = None,
                  run_record: dict[str, Any] | None = None) -> dict[str, float | None]:
    """Feature mapping ("block.name" -> number) built from the submission's own code.

    Static and semantic features come from the source. Compiler-warning counts
    are used when the caller has them; otherwise the whole warnings block is absent.
    `run_record` (the shape scripts/counterfactual_evidence.py writes) supplies the
    `evidence` and `repair` blocks; without it they are absent, and the `execution`
    variant abstains because too many of its features are missing.
    """
    from tracelearn_features.execution import execution_blocks
    from tracelearn_features.normalize import normalize_row, runner_warnings
    from tracelearn_features.schema import feature_names

    # A run record carries the warnings the training rows were given, so it wins.
    measured = runner_warnings(run_record, language)
    row = {"dataset_source": "CODESTREAM", "language": language, "warnings": measured if measured is not None else warnings}
    normalized = normalize_row(row, code=source)
    normalized.update(execution_blocks(run_record))
    out: dict[str, float | None] = {}
    for name in feature_names():
        block, _, short = name.partition(".")
        value = (normalized.get(block) or {}).get(short)
        if isinstance(value, bool):
            value = float(value)
        out[name] = value if isinstance(value, (int, float)) and math.isfinite(value) else None
    return out


def compiler_warnings(source: str) -> dict[str, Any] | None:
    """Compile (never run) the submission with the warning flags the model was trained on.

    Returns `{"compile_warnings": <gcc text>}`, or None when the code does not compile, is
    rejected by the sandbox's directive filter, or the compiler is unavailable; the model then
    sees the warnings block as missing and abstains instead of guessing. Runs inside the same
    sandbox as the test runner, with the same time and memory limits.
    """
    try:
        from pathlib import Path

        from backend.app.execution.cpp_runner import COMPILER_MEMORY_MB, CPP_STANDARD
        from backend.app.execution.sandbox import check_cpp_source, clean_compiler_output, new_workdir, run_in_sandbox

        if check_cpp_source(source):
            return None
        tmp = new_workdir()
        try:
            workdir = Path(tmp.name)
            (workdir / "solution.cpp").write_text(source, encoding="utf-8")
            res = run_in_sandbox(["g++", f"-std={CPP_STANDARD}", *WARNING_FLAGS, "-c", "solution.cpp", "-o", "solution.o"],
                                 workdir, timeout=settings.compile_timeout_seconds, memory_mb=COMPILER_MEMORY_MB,
                                 output_bytes=8 * 1024 * 1024)
            if res.timed_out or res.returncode != 0:
                return None
            return {"compile_warnings": clean_compiler_output(res.stderr, workdir) or ""}
        finally:
            tmp.cleanup()
    except Exception:
        log.exception("compiling for warning counts failed; the model will abstain")
        return None


def predict_source(source: str, language: str = "cpp", warnings: dict[str, Any] | None = None,
                   run_record: dict[str, Any] | None = None) -> ModelPrediction | None:
    if len(source) > MAX_SOURCE_CHARS or not source.strip():
        return None
    features = code_features(source, language, warnings, run_record)
    # Repair-first stage: when exactly one class's repair fixes every test, that class
    # replaces the model's label (about 0.9 precision on real rows; see repair_override).
    # The model still runs so the prediction keeps its top-k and probabilities for display.
    override = repair_override(features)
    if override is not None:
        clf = _classifier(settings.model_variant, str(settings.model_dir))
        pred = clf.predict(features)
        import dataclasses  # noqa: PLC0415
        return dataclasses.replace(
            pred,
            top_label=override,
            top_probability=1.0,
            abstained=False,
        )
    clf = _classifier(settings.model_variant, str(settings.model_dir))
    return clf.predict(features)


def execution_shadow_record(source: str, run_record: dict[str, Any], language: str = "cpp") -> EvidenceRecord | None:
    """What the `execution` model would say for this run record, as weightless evidence."""
    if len(source) > MAX_SOURCE_CHARS or not source.strip():
        return None
    pred = _classifier("execution", str(settings.model_dir)).predict(code_features(source, language, None, run_record))
    if pred.n_features and pred.n_missing / pred.n_features > MAX_MISSING_SHARE and not pred.abstained:
        pred = dataclasses.replace(pred, abstained=True)
    return EvidenceRecord(
        source_type="model", evidence_code="MODEL_SHADOW", direction="neutral", weight=0.0,
        description=(f"Shadow mode: the execution classifier would say {pred.top_label} "
                     f"at {pred.top_probability:.2f}{' (abstained)' if pred.abstained else ''}; not used."),
        details=pred.as_dict())


def model_records(source: str, language: str = "cpp", warnings: dict[str, Any] | None = None,
                  run_record: dict[str, Any] | None = None) -> list[EvidenceRecord]:
    """Zero or one evidence record for this submission, according to `model_diagnosis`."""
    mode = settings.model_diagnosis
    if mode == "off":
        return []
    try:
        if warnings is None:
            warnings = compiler_warnings(source)
        pred = predict_source(source, language, warnings, run_record)
        if pred is None:
            return []
        if pred.n_features and pred.n_missing / pred.n_features > MAX_MISSING_SHARE and not pred.abstained:
            pred = dataclasses.replace(pred, abstained=True)
        if mode == "shadow":
            return [EvidenceRecord(
                source_type="model", evidence_code="MODEL_SHADOW", direction="neutral", weight=0.0,
                description=(f"Shadow mode: the classifier would say {pred.top_label} "
                             f"at {pred.top_probability:.2f}{' (abstained)' if pred.abstained else ''}; not used."),
                details=pred.as_dict())]
        return [model_evidence(pred)]
    except Exception:  # the rules must still diagnose
        log.exception("model diagnosis failed; continuing with rules only")
        return []
