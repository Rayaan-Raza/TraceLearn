"""End-to-end pipeline test (I13): full feature builder → classifier flow on real .cpp files.

Verifies that the served variant produces valid, well-formed predictions on
actual diagnostic C++ source files without crashing or returning malformed
output.  Intentionally does not assert specific labels — the data distribution
makes that brittle — but checks structural invariants that must always hold.
"""
from __future__ import annotations

import glob
import math
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CPP_GLOB = str(REPO_ROOT / "data" / "cpp_diagnostics" / "**" / "*.cpp")


@pytest.fixture(scope="module")
def cpp_files():
    files = sorted(glob.glob(CPP_GLOB, recursive=True))
    if not files:
        pytest.skip("No .cpp diagnostic files found — skipping e2e pipeline test")
    return files


@pytest.fixture(scope="module")
def classifier():
    from backend.app.diagnosis.xgb_classifier import ModelClassifier, ModelContractError
    try:
        return ModelClassifier.load("best")
    except (ModelContractError, FileNotFoundError):
        pytest.skip("Model artifacts not available")


@pytest.fixture(scope="module")
def builder():
    from backend.app.analysis.model_features import InferenceFeatureBuilder
    return InferenceFeatureBuilder()


class TestFullPipelineE2E:
    def test_at_least_fifty_files_in_corpus(self, cpp_files):
        assert len(cpp_files) >= 50, f"Expected ≥50 .cpp files, found {len(cpp_files)}"

    def test_prediction_has_valid_structure(self, classifier, builder, cpp_files):
        source = Path(cpp_files[0]).read_text(encoding="utf-8", errors="replace")
        features = builder.build(source=source, compile_stderr="", test_results=None)
        pred = classifier.predict(features)
        assert pred.top_label is not None
        assert 0.0 <= pred.top_probability <= 1.0
        assert isinstance(pred.abstained, bool)
        assert pred.n_features >= 1
        assert pred.n_missing >= 0
        assert pred.n_missing < pred.n_features or pred.n_features > 0

    def test_probabilities_sum_to_one(self, classifier, builder, cpp_files):
        source = Path(cpp_files[0]).read_text(encoding="utf-8", errors="replace")
        features = builder.build(source=source, compile_stderr="", test_results=None)
        pred = classifier.predict(features)
        total = sum(pred.probabilities.values())
        assert abs(total - 1.0) < 1e-4, f"Probabilities sum to {total:.6f}, expected ~1.0"

    def test_top_k_matches_probabilities(self, classifier, builder, cpp_files):
        source = Path(cpp_files[0]).read_text(encoding="utf-8", errors="replace")
        features = builder.build(source=source, compile_stderr="", test_results=None)
        pred = classifier.predict(features)
        # top_k[0] should match top_label and top_probability
        assert pred.top_k[0][0] == pred.top_label
        assert abs(pred.top_k[0][1] - pred.top_probability) < 1e-6

    def test_pipeline_does_not_crash_on_all_corpus_files(self, classifier, builder, cpp_files):
        failures = []
        for path in cpp_files[:30]:
            try:
                source = Path(path).read_text(encoding="utf-8", errors="replace")
                features = builder.build(source=source, compile_stderr="", test_results=None)
                pred = classifier.predict(features)
                assert pred.top_label is not None
            except Exception as exc:
                failures.append(f"{path}: {exc}")
        assert not failures, f"Pipeline crashed on {len(failures)} files:\n" + "\n".join(failures)

    def test_nonzero_features_used_on_real_source(self, classifier, builder, cpp_files):
        source = Path(cpp_files[0]).read_text(encoding="utf-8", errors="replace")
        features = builder.build(source=source, compile_stderr="", test_results=None)
        pred = classifier.predict(features)
        # At minimum, static block features should be present (not all missing)
        assert pred.n_missing < pred.n_features, \
            f"All {pred.n_features} features are missing; expected at least some to be populated"
