"""Run a whole job inside the pinned sandbox image.

The container gives the isolation items of Master Plan §9.2-U0 that the local
backend cannot: ``--network none``, read-only root, tmpfs work area, non-root
user, ``--pids-limit``, ``--memory`` and a CPU limit. Inside, the job runs
through the local backend, so results are byte-for-byte the same shape.

Pin the image by digest (``tracelearn-sandbox@sha256:...``); the digest is
recorded in the G0b manifest by ``scripts/sandbox_manifest.py``.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import subprocess
import tempfile

from .config import RunConfig

DEFAULT_IMAGE = os.environ.get("SANDBOX_IMAGE", "tracelearn-sandbox:0.2.0")


def docker_argv(image: str, jobdir: str, cfg: RunConfig) -> list[str]:
    lim = cfg.limits
    return [
        "docker", "run", "--rm", "-i",
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:rw,exec,nosuid,size=256m",
        "--user", "65534:65534",
        "--pids-limit", str(lim.pids),
        "--memory", f"{lim.memory_mb * 2}m",  # sanitizer shadow memory needs headroom
        "--memory-swap", f"{lim.memory_mb * 2}m",
        "--cpus", "1",
        "--ulimit", f"stack={lim.stack_mb * 1024 * 1024}",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "-e", f"SANDBOX_IMAGE_DIGEST={image}",
        "-v", f"{jobdir}:/job:ro",
        image,
        "python3", "-m", "sandbox_runner.cli", "run-job", "/job/job.json",
    ]


def run_in_docker(code: str, lang: str, tests: list[dict], cfg: RunConfig,
                  image: str | None = None) -> dict:
    image = image or DEFAULT_IMAGE
    if not shutil.which("docker"):
        raise RuntimeError("docker backend requested but docker is not installed")
    jobdir = tempfile.mkdtemp(prefix="sbxjob-")
    try:
        job = {"code": code, "lang": lang, "tests": tests,
               "config": dataclasses.asdict(cfg)}
        with open(os.path.join(jobdir, "job.json"), "w", encoding="utf-8") as f:
            json.dump(job, f)
        os.chmod(jobdir, 0o755)
        os.chmod(os.path.join(jobdir, "job.json"), 0o644)
        budget = (cfg.limits.compile_time_s * 3
                  + len(tests) * cfg.limits.time_s * (2 + cfg.limits.sanitizer_time_factor)
                  + cfg.limits.time_s * cfg.limits.valgrind_time_factor * 2 + 30)
        r = subprocess.run(docker_argv(image, jobdir, cfg), capture_output=True, text=True,
                           timeout=budget)
        if r.returncode != 0:
            raise RuntimeError(f"docker job failed rc={r.returncode}: {r.stderr[-500:]}")
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(jobdir, ignore_errors=True)
