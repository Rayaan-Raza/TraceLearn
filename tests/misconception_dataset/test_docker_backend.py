"""The docker backend gives the same answers as the local backend (G0b).

Runs only when SANDBOX_IMAGE names a built sandbox image and Docker is
reachable — the dataset CI workflow builds the image and sets it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from sandbox_runner import RunConfig, run_submission

FIX = Path(__file__).resolve().parents[2] / "data" / "misconception_dataset" / "fixtures" / "sandbox"
IMAGE = os.environ.get("SANDBOX_IMAGE")


def _docker_ok() -> bool:
    if not IMAGE or not shutil.which("docker"):
        return False
    r = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True)
    return r.returncode == 0


pytestmark = pytest.mark.skipif(not _docker_ok(), reason="set SANDBOX_IMAGE to a built sandbox image")


def T(i, o):
    return {"input": i, "output": o}


def both(name, tests, cfg=None):
    cfg = cfg or RunConfig(double_run=False)
    code = (FIX / name).read_text()
    lang = "c" if name.endswith(".c") else "cpp"
    return (run_submission(code, lang, tests, cfg, backend="local"),
            run_submission(code, lang, tests, cfg, backend="docker", image=IMAGE))


def key(r):
    t = r.get("tests") or {}
    rt = r.get("runtime") or {}
    return {"branch": r.get("branch"), "compile_ok": r["compile"]["ok"],
            "statuses": [x["status"] for x in t.get("results", [])],
            "san_kinds": sorted(((rt.get("sanitizer") or {}).get("kinds") or {})),
            "vg_uninit": (rt.get("valgrind") or {}).get("uninit")}


@pytest.mark.parametrize("name,tests", [
    ("clean.cpp", [T("3\n", "6\n"), T("4\n", "1\n")]),
    ("asan_overflow.cpp", [T("4\n", "0\n")]),
    ("ubsan_overflow.cpp", [T("3\n", "1000\n"), T("12\n", "1000000000000\n")]),
    ("compile_error.cpp", [T("1\n", "1\n")]),
    ("c_bool.c", [T("3\n", "yes\n")]),
])
def test_docker_matches_local(name, tests):
    local, docker = both(name, tests)
    assert docker["backend"] == "docker"
    assert key(docker) == key(local)


def test_docker_valgrind_uninit():
    cfg = RunConfig(double_run=False, sanitizer_pass=False)
    code = (FIX / "uninit.cpp").read_text()
    r = run_submission(code, "c", [T("3\n", "6\n")], cfg, backend="docker", image=IMAGE)
    assert r["runtime"]["valgrind"]["ran"] and r["runtime"]["valgrind"]["uninit"]


def test_docker_has_no_network():
    code = (FIX / "network.cpp").read_text()
    r = run_submission(code, "cpp", [T("", "blocked\n")], RunConfig(double_run=False, valgrind_pass=False),
                       backend="docker", image=IMAGE)
    assert r["tests"]["all_passed"]


def test_docker_timeout_is_enforced():
    cfg = RunConfig(double_run=False, sanitizer_pass=False, valgrind_pass=False)
    code = (FIX / "timeout.cpp").read_text()
    r = run_submission(code, "cpp", [T("5\n", "5\n")], cfg, backend="docker", image=IMAGE)
    assert r["tests"]["results"][0]["status"] == "timeout"
