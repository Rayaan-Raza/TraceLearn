"""Write the G0b environment manifest for sandbox_runner.

    python scripts/sandbox_manifest.py [--image tracelearn-sandbox:0.2.0] \
        [--out data/misconception_dataset/raw_recovery/recovery_manifest_lane_b.json]

Records compiler / Valgrind / Python versions, compile flags, limits, which
isolation the local backend achieves on this host, the Docker image id (when
an image is given and Docker is reachable) and the Python 3.14 wheel check.
The G0b evidence lives in its own per-lane file (``recovery_manifest_lane_b.json``
— team merge decision: each lane keeps its own manifest so no lane's provenance
overwrites another's); the ``environment`` section is merged across re-runs of
this script.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sandbox_runner import SANDBOX_VERSION, RunConfig  # noqa: E402
from sandbox_runner import config as C  # noqa: E402
from sandbox_runner.process import isolation_report  # noqa: E402
from sandbox_runner.toolchain import toolchain_versions  # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "data", "misconception_dataset", "raw_recovery",
                           "recovery_manifest_lane_b.json")
WHEELS = ["xgboost", "shap", "pandas", "scikit-learn"]


def docker_image_info(image: str) -> dict:
    if not shutil.which("docker"):
        return {"image": image, "status": "docker not installed"}
    r = subprocess.run(["docker", "image", "inspect", image, "--format",
                        "{{.Id}} {{json .RepoDigests}}"], capture_output=True, text=True)
    if r.returncode != 0:
        return {"image": image, "status": "not built", "stderr": r.stderr.strip()[-300:]}
    img_id, digests = r.stdout.strip().split(" ", 1)
    return {"image": image, "status": "ok", "id": img_id, "repo_digests": json.loads(digests)}


def wheel_check(py: str = "3.14") -> dict:
    out = {}
    for plat in ("win_amd64", "manylinux_2_28_x86_64"):
        res = {}
        for pkg in WHEELS:
            r = subprocess.run([sys.executable, "-m", "pip", "download", pkg, "--only-binary=:all:",
                                "--python-version", py, "--platform", plat, "--no-deps", "-d",
                                os.path.join(os.environ.get("TMPDIR", "/tmp"), "wheelcheck"), "-q"],
                               capture_output=True, text=True)
            res[pkg] = r.returncode == 0
        out[plat] = res
    ok = all(all(v.values()) for v in out.values())
    return {"python": py, "platforms": out, "decision": f"python {py}" if ok else "pin python 3.12"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=None)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--skip-wheels", action="store_true")
    a = ap.parse_args()
    cfg = RunConfig()
    env = {
        "gate": "G0b",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sandbox_version": SANDBOX_VERSION,
        "config_fingerprint": cfg.fingerprint(),
        "toolchain": toolchain_versions(),
        "std": C.LANG_STD,
        "flags": {"warnings_and_exec": C.WARNING_FLAGS, "sanitizer": C.SANITIZER_FLAGS,
                  "valgrind_build": C.VALGRIND_FLAGS, "asan_options": C.ASAN_OPTIONS,
                  "ubsan_options": C.UBSAN_OPTIONS},
        "limits": cfg.to_dict()["limits"],
        "local_isolation": isolation_report(),
        "docker": docker_image_info(a.image) if a.image else {"status": "no image given"},
    }
    if not a.skip_wheels:
        env["wheel_check"] = wheel_check()
    manifest = {}
    if os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as f:
            manifest = json.load(f)
    manifest["environment"] = env
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print(json.dumps(env, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
