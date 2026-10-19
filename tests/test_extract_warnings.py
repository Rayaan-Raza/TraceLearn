"""TDD for scripts/extract_progpedia_warnings.py (Task 7, pg-1/pg-4 warnings).

Scope ruling: PROGPEDIA x language in {c, cpp} only — Java/Python are out of
the lane (Java has no gcc; Python has no compiler warnings at all).
"""

import json

import pytest

from scripts.extract_progpedia_warnings import (
    assemble_rows,
    build_jobs,
    run_extraction,
    select_rows,
    wsl_path,
)

RAW = r"G:\TraceLearn\Datasets_RAW"


def _row(record_id="00000006/ACCEPTED/00002_00005/Prob_F.c", *, lang="c",
         sha="a" * 64, source="PROGPEDIA", path="progpedia/00000006/ACCEPTED/00002_00005/Prob_F.c"):
    return {
        "source_record_id": record_id,
        "dataset_source": source,
        "language": lang,
        "source_code_sha256": sha,
        "source_code_path": path,
    }


# ---------------------------------------------------------------- select_rows


def test_select_keeps_only_progpedia_c_cpp():
    rows = [
        _row("pg/c", lang="c"),
        _row("pg/cpp", lang="cpp"),
        _row("pg/java", lang="java"),
        _row("pg/python", lang="python"),
        _row("cs/c", source="CODESTREAM"),
    ]
    got = select_rows(rows)
    assert [r["source_record_id"] for r in got] == ["pg/c", "pg/cpp"]


# ----------------------------------------------------------------- build_jobs


def test_build_jobs_dedupes_by_compiler_and_sha():
    rows = [
        _row("rec1", sha="b" * 64),
        _row("rec2", sha="b" * 64),          # identical content, same compiler
        _row("rec3", lang="cpp", sha="b" * 64, path="progpedia/x/y/z.cpp"),  # same bytes, other compiler
    ]
    jobs = build_jobs(rows, __import__("pathlib").Path(RAW))
    assert len(jobs) == 2
    by_key = {(j["compiler"], j["sha256"]): j for j in jobs}
    assert set(by_key) == {("gcc", "b" * 64), ("g++", "b" * 64)}
    assert by_key[("gcc", "b" * 64)]["record_ids"] == ["rec1", "rec2"]
    # deterministic order
    assert jobs == sorted(jobs, key=lambda j: (j["compiler"], j["sha256"]))


def test_build_jobs_resolves_path_under_raw_root_and_flags_missing():
    import pathlib

    rows = [
        _row("exists", path="progpedia/00000006/ACCEPTED/00002_00005/Prob_F.c"),
        _row("missing", sha="c" * 64, path="progpedia/does/not/exist.c"),
    ]
    jobs = build_jobs(rows, pathlib.Path(RAW))
    exists = next(j for j in jobs if j["record_ids"] == ["exists"])
    missing = next(j for j in jobs if j["record_ids"] == ["missing"])
    assert exists["path"] == pathlib.Path(RAW) / "progpedia/00000006/ACCEPTED/00002_00005/Prob_F.c"
    assert exists["exists"] is True
    assert missing["exists"] is False


def test_wsl_path_converts_windows_drive():
    import pathlib

    assert wsl_path(pathlib.Path(r"G:\TraceLearn\datasets\x.c")) == "/mnt/g/TraceLearn/datasets/x.c"


# -------------------------------------------------------------- run_extraction


class FakeRunner:
    """Stands in for the WSL batch: writes canned stderr per (compiler, sha)."""

    def __init__(self, script_by_key=None, exit_code=0):
        self.calls = 0
        self.script_by_key = script_by_key or {}
        self.exit_code = exit_code

    def __call__(self, jobs, work_dir, workers):
        self.calls += 1
        for j in jobs:
            key = f'{j["compiler"]}-{j["sha256"]}'
            stderr, code = self.script_by_key.get(key, ("", self.exit_code))
            (work_dir / f"{key}.err").write_text(stderr, encoding="utf-8")
            (work_dir / f"{key}.exit").write_text(str(code), encoding="utf-8")


PAREN_WARN = (
    "Prob_F.c:5:7: warning: suggest parentheses around assignment used as truth "
    "value [-Wparentheses]\n"
)


def test_run_extraction_parses_flags_into_rows(tmp_path):
    raw = tmp_path / "raw"
    src = raw / "progpedia/p/v/s/Prob_F.c"
    src.parent.mkdir(parents=True)
    src.write_text("int main(){return 0;}\n", encoding="utf-8")
    work = tmp_path / "work"
    rows = [_row(path="progpedia/p/v/s/Prob_F.c")]

    runner = FakeRunner({f"gcc-{'a' * 64}": (PAREN_WARN, 0)})
    out = run_extraction(rows, raw, work, runner=runner, workers=4)

    assert runner.calls == 1
    assert out[0]["source_record_id"] == rows[0]["source_record_id"]
    assert out[0]["compile_ok"] is True
    flags = json.loads(out[0]["flags"])
    assert {"flag": "-Wparentheses", "count": 1} in flags


def test_run_extraction_is_resumable(tmp_path):
    raw = tmp_path / "raw"
    src = raw / "progpedia/p/v/s/a.c"
    src.parent.mkdir(parents=True)
    src.write_text("int main(){return 0;}\n", encoding="utf-8")
    work = tmp_path / "work"
    rows = [_row(path="progpedia/p/v/s/a.c")]

    runner = FakeRunner()
    run_extraction(rows, raw, work, runner=runner, workers=4)
    first_calls = runner.calls
    run_extraction(rows, raw, work, runner=runner, workers=4)  # cached work dir
    assert runner.calls == first_calls  # no recompile of finished jobs


def test_timeout_produces_null_flags_never_partial(tmp_path):
    raw = tmp_path / "raw"
    src = raw / "progpedia/p/v/s/t.c"
    src.parent.mkdir(parents=True)
    src.write_text("int main(){return 0;}\n", encoding="utf-8")
    rows = [_row(path="progpedia/p/v/s/t.c")]

    runner = FakeRunner({f"gcc-{'a' * 64}": (PAREN_WARN, 124)})  # GNU timeout exit
    out = run_extraction(rows, raw, tmp_path / "work", runner=runner, workers=4)
    assert out[0]["compile_ok"] is False
    assert out[0]["flags"] is None           # incomplete evidence -> null (§6)


def test_missing_source_row_is_null_not_guessed(tmp_path):
    rows = [_row(path="progpedia/gone.c", sha="d" * 64)]
    runner = FakeRunner()
    out = run_extraction(rows, tmp_path / "raw", tmp_path / "work", runner=runner)
    assert runner.calls == 0                 # nothing to compile
    assert out[0]["compile_ok"] is None
    assert out[0]["flags"] is None


def test_wsl_compile_manifest_and_script_are_lf_only(tmp_path, monkeypatch):
    """Regression: a CRLF manifest makes every `$src` end in \\r, so the bash
    `[ -f ]` check reports 'missing' for all files (first real run: exit 127
    on all 2339 jobs)."""
    import scripts.extract_progpedia_warnings as m

    class _Proc:
        returncode = 0
        stderr = ""
        stdout = ""

    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: _Proc())
    job = {"compiler": "gcc", "sha256": "e" * 64, "path": RAW + r"\x\y.c",
           "exists": True, "record_ids": ["r"]}
    work = tmp_path / "w"
    m.wsl_compile([job], work, 4)
    manifest = (work / "manifest.tsv").read_bytes()
    script = (work / "run.sh").read_bytes()
    assert b"\r" not in manifest and manifest.endswith(b"\n")
    assert b"\r" not in script
    # full codegen, not -fsyntax-only (dataflow warnings need it, §3.4 pg-4)
    assert b" -c -O2 -Wall -o /dev/null " in script


# --------------------------------------------------------------- assemble_rows


def test_assemble_rows_deterministic_and_sorted(tmp_path):
    rows = [
        _row("rec/z", sha="f" * 64),
        _row("rec/a", sha="e" * 64),
    ]
    results = {("gcc", "f" * 64): {"compile_ok": True, "flags": []},
               ("gcc", "e" * 64): {"compile_ok": True, "flags": []}}
    out = assemble_rows(rows, results)
    assert [r["source_record_id"] for r in out] == ["rec/a", "rec/z"]
    assert out[0]["flags"] == json.dumps([])
