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


# ---- U6: memory limits inside the image -------------------------------------

BOMB = r"""#include <cstdio>
#include <cstdlib>
#include <cstring>
int main(){ long mb=0; for(;;){ char*p=(char*)malloc(16<<20);
  if(!p){printf("alloc_failed_at_mb=%ld\n",mb);return 3;}
  memset(p,1,16<<20); mb+=16; } }
"""


def _stopped_at_mb(res: dict) -> int:
    head = res["stdout_head"]
    assert "alloc_failed_at_mb=" in head, f"allocation was not refused: {head!r}"
    return int(head.split("alloc_failed_at_mb=")[1].split()[0])


def test_docker_memory_bomb_stops_at_the_limit():
    """A C++ program that allocates until it is refused stops under the per-process cap."""
    cfg = RunConfig(double_run=False, valgrind_pass=False)
    r = run_submission(BOMB, "cpp", [T("", "x")], cfg, backend="docker", image=IMAGE)
    stopped = _stopped_at_mb(r["tests"]["results"][0])
    print(f"memory bomb stopped at {stopped} MB (limit {cfg.limits.memory_mb} MB)")
    assert 0 < stopped <= cfg.limits.memory_mb


def test_docker_limit_applies_to_every_test_run_not_only_the_first():
    """The run-record path runs many programs one after another; each gets its own cap."""
    cfg = RunConfig(double_run=False, valgrind_pass=False, sanitizer_pass=False, stop_after_timeouts=99)
    r = run_submission(BOMB, "cpp", [T("", "x")] * 3, cfg, backend="docker", image=IMAGE)
    stops = [_stopped_at_mb(x) for x in r["tests"]["results"]]
    assert len(stops) == 3 and all(0 < s <= cfg.limits.memory_mb for s in stops), stops


def test_docker_container_kills_a_process_that_has_no_address_cap(tmp_path):
    """Sanitizer and valgrind runs lift the per-process cap, so the container's own limit is what
    stops them. Run the image with the exact flags the backend uses and allocate past them."""
    from sandbox_runner.docker_backend import docker_argv
    cfg = RunConfig()
    flags = docker_argv(IMAGE, str(tmp_path), cfg)
    flags = flags[: flags.index("-e")]  # keep the resource and isolation flags, drop env/mount/command
    argv = [*flags, IMAGE, "python3", "-c", "b = [bytearray(64 << 20) for _ in iter(int, 1)]"]
    p = subprocess.run(argv, capture_output=True, timeout=120)
    limit = cfg.limits.memory_mb * 2
    print(f"uncapped process killed by the container at {limit} MB: exit {p.returncode}")
    assert p.returncode == 137  # SIGKILL from the cgroup OOM killer
