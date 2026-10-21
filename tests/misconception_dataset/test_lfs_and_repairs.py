"""Must-fire / must-not-fire fixtures for every Lane B LF, plus repair-and-rerun
(Master Plan §5-U2: "unit-tested must-fire/must-not-fire fixtures")."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from codestream_lfs import beta_lower, confidence
from codestream_static import blank, parse
from label_weak_codestream import decide
from repair_verify import candidates
from sandbox_runner import RunConfig, run_submission

FIX = Path(__file__).resolve().parents[2] / "data" / "misconception_dataset" / "fixtures" / "lfs"
HAS_GCC = shutil.which("g++") is not None
HAS_VG = shutil.which("valgrind") is not None
gcc = pytest.mark.skipif(not HAS_GCC, reason="needs g++")


def _load(stem):
    src = next(FIX.glob(stem + ".c*"))
    tests_name = stem.replace("_fire", "_fire") + ".tests.json"
    tests = json.loads((FIX / tests_name).read_text())
    lang = "c" if src.suffix == ".c" else "cpp"
    return src.read_text(), lang, tests


def _decide(stem, valgrind=False):
    code, lang, tests = _load(stem)
    cfg = RunConfig(valgrind_pass=valgrind, double_run=False)
    res = run_submission(code, lang, tests, cfg)
    return decide(code, lang, tests, res)


# ------------------------------------------------------------ static ----

def test_blank_keeps_offsets_and_hides_strings():
    code = 'int main(){ printf("a < b; for(;;)"); // i <= n\n return 0; }'
    b = blank(code)
    assert len(b) == len(code)
    assert "for" not in b and "<=" not in b
    assert b.index("return") == code.index("return")


def test_parse_finds_loops_conditions_functions():
    code = "int f(int n){ if (n == 0) return 1; return n*f(n-1); }\n" \
           "int main(){ int a[10], s; for (int i = 0; i <= 9; i++) a[i] = i; while (s > 0) {} }"
    p = parse(code)
    assert [l.kind for l in p.loops] == ["for", "while"]
    assert {f.name for f in p.functions} == {"f", "main"}
    assert any(d.var == "a" and d.array_size == "10" for d in p.decls)
    assert any(d.var == "s" and not d.initialized for d in p.decls)


def test_repair_candidates_are_minimal_edits():
    code = "int main(){ int n=3; for (int i = 0; i <= n; i++) {} }"
    reps = candidates(code, "CPP_LOOP_BOUNDARY")
    assert reps and reps[0].after == "<"
    assert reps[0].code == code.replace("i <= n", "i < n")


# ----------------------------------------------------------- confidence --

def test_beta_lower_bound():
    assert beta_lower(0, 0) == pytest.approx(0.2, abs=1e-3)
    assert 0.94 < beta_lower(50, 50) < 0.98
    assert beta_lower(45, 50) < beta_lower(50, 50)
    assert confidence("lf_x", {"lf_x": (100, 100)})[0] == 0.85  # source cap


# ------------------------------------------------------------ must-fire --

@gcc
@pytest.mark.parametrize("stem,cls,decision", [
    ("loop_boundary_fire", "CPP_LOOP_BOUNDARY", "repair_verified"),
    ("off_by_one_fire", "CPP_OFF_BY_ONE", "repair_verified"),
    ("array_bounds_fire", "CPP_ARRAY_BOUNDS", "repair_verified"),
    ("int_overflow_fire", "CPP_INT_OVERFLOW", "repair_verified"),
    ("missing_base_case_fire", "CPP_MISSING_BASE_CASE", "repair_verified"),
    ("assign_vs_compare_fire", "CPP_ASSIGN_VS_COMPARE", "repair_verified"),
    ("wrong_loop_dir_fire", "CPP_WRONG_LOOP_DIR", "discovery"),
    ("range_check_fire", "CPP_RANGE_CHECK", "discovery"),
])
def test_must_fire(stem, cls, decision):
    d = _decide(stem)
    assert cls in d["fired_classes"], d["fired_classes"]
    assert d["decision"] == decision, (d["decision"], d.get("verified_classes"))
    assert d["label"] == cls


@gcc
@pytest.mark.skipif(not HAS_VG, reason="needs valgrind")
def test_must_fire_uninit_detector_and_repair():
    d = _decide("uninit_fire", valgrind=True)
    assert "CPP_UNINITIALIZED_VAR" in d["fired_classes"]
    assert d["decision"] == "discovery" and d["label"] == "CPP_UNINITIALIZED_VAR"


@gcc
def test_stale_exit_detector_fires_but_timeout_is_a_pre_branch():
    code, lang, tests = _load("stale_exit_fire")
    res = run_submission(code, lang, tests, RunConfig(valgrind_pass=False, double_run=False))
    assert res["branch"] == "timeout_only"
    assert _decide("stale_exit_fire")["decision"] == "pre_branch"
    from codestream_lfs import Ctx, lf_stale_exit_detector
    f = lf_stale_exit_detector(Ctx(code, parse(code), res, tests))
    assert f and f.cls == "CPP_STALE_EXIT" and f.evidence["cond_vars"] == ["n"]


# -------------------------------------------------------- must-not-fire --

@gcc
def test_clean_program_is_pre_branch():
    assert _decide("clean_sum")["decision"] == "pre_branch"


@gcc
def test_other_error_does_not_fire_and_is_never_labeled_other():
    d = _decide("other_error")
    assert d["fired_classes"] == []
    assert d["decision"] == "no_fire" and d["label"] is None


@gcc
def test_loop_boundary_lf_does_not_fire_on_big_delta():
    code, lang, tests = _load("other_error")
    res = run_submission(code, lang, tests, RunConfig(valgrind_pass=False, double_run=False))
    from codestream_lfs import Ctx, lf_loop_boundary, lf_off_by_one
    ctx = Ctx(code, parse(code), res, tests)
    assert lf_loop_boundary(ctx) is None and lf_off_by_one(ctx) is None
