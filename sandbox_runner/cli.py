"""Command line entry points.

    python -m sandbox_runner.cli run FILE.cpp --tests tests.json [--lang cpp]
    python -m sandbox_runner.cli run-job job.json        # used inside the container
    python -m sandbox_runner.cli env                     # toolchain + isolation report
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import Limits, RunConfig


def _cfg_from_dict(d: dict) -> RunConfig:
    d = dict(d)
    lim = Limits(**d.pop("limits", {}))
    return RunConfig(limits=lim, **d)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sandbox_runner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("source")
    r.add_argument("--tests", required=True, help="JSON list of {input, output}")
    r.add_argument("--lang", default=None)
    r.add_argument("--backend", default="local", choices=["local", "docker"])
    r.add_argument("--image", default=None)
    r.add_argument("--no-valgrind", action="store_true")
    j = sub.add_parser("run-job")
    j.add_argument("job")
    sub.add_parser("env")
    a = ap.parse_args(argv)

    from .runner import run_submission
    if a.cmd == "run":
        code = open(a.source, encoding="utf-8").read()
        lang = a.lang or ("c" if a.source.endswith(".c") else "cpp")
        tests = json.load(open(a.tests, encoding="utf-8"))
        cfg = RunConfig(valgrind_pass=not a.no_valgrind)
        res = run_submission(code, lang, tests, cfg, backend=a.backend, image=a.image)
    elif a.cmd == "run-job":
        job = json.load(open(a.job, encoding="utf-8"))
        res = run_submission(job["code"], job["lang"], job["tests"],
                             _cfg_from_dict(job["config"]), backend="local")
    else:
        from .process import isolation_report
        from .toolchain import toolchain_versions
        res = {"toolchain": toolchain_versions(), "isolation": isolation_report(),
               "config": RunConfig().to_dict()}
    json.dump(res, sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
