"""Build oracle tests for PROGPedia problems from agreeing ACCEPTED submissions.

PROGPedia has verdict folders but no tests, so its rows could only be
labeled from code shape (pg rules) — which yields CPP_ARRAY_BOUNDS only.
This script gives every usable problem real tests:

1. inputs: the statement's sample inputs + seeded generated inputs
   (``progpedia_generators.py``: small / medium / edge / large);
2. expected output: run up to ``--oracles`` ACCEPTED C/C++ submissions of the
   same problem; a test is kept only when at least 2 oracles agree token for
   token and the agreeing group is at least 2/3 of the oracles that finished;
3. samples double as a sanity check: the consensus must match the
   statement's own sample output, or the whole problem is dropped.

    python scripts/progpedia_oracle_tests.py --raw-root <dir with progpedia/ and "progpedia (1)/">

Output: ``data/misconception_dataset/oracle_tests/progpedia/<problem>.json.gz``
(inputs above 64 KB are not stored — they are regenerated from ``gen_seed``,
and ``input_sha256`` guards the regeneration) plus a report.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import progpedia_generators as gen  # noqa: E402

from sandbox_runner.config import Limits  # noqa: E402
from sandbox_runner.process import run_process  # noqa: E402

OUT_DIR = ROOT / "data" / "misconception_dataset" / "oracle_tests" / "progpedia"
REPORT = ROOT / "data" / "misconception_dataset" / "reports" / "progpedia_oracle_tests.md"
GENERATOR_VERSION = "progpedia_generators/1.0"
STORE_LIMIT = 64 * 1024
COPIES = ("progpedia", "progpedia (1)")
LIMITS = Limits(time_s=4.0, output_bytes=8 << 20)


def problem_dirs(raw_root: Path, problem_id: str) -> list[Path]:
    num = problem_id.rsplit("-", 1)[1]
    return [raw_root / c / num for c in COPIES if (raw_root / c / num).is_dir()]


def submissions(raw_root: Path, problem_id: str, verdict: str) -> list[Path]:
    out = []
    for d in problem_dirs(raw_root, problem_id):
        vd = d / verdict
        if vd.is_dir():
            out += sorted(p for p in vd.rglob("*") if p.suffix in (".c", ".cpp", ".cc"))
    return out


def statement_samples(raw_root: Path, problem_id: str) -> list[dict]:
    """Parse '### Input n' / '### Output n' fenced blocks from statement.md."""
    for d in problem_dirs(raw_root, problem_id):
        st = d / "statement.md"
        if st.exists():
            text = st.read_text(encoding="utf-8", errors="replace")
            blocks = re.findall(r"###\s*(Input|Output)\s*(\d*)\s*\n+```[a-z]*\n(.*?)```", text, re.S | re.I)
            ins = [(n or "1", b) for kind, n, b in blocks if kind.lower() == "input"]
            outs = {n or "1": b for kind, n, b in blocks if kind.lower() == "output"}
            return [{"kind": "sample", "gen_seed": None, "input": b, "statement_output": outs[n]}
                    for n, b in ins if n in outs]
    return []


def compile_source(path: Path, workdir: str) -> str | None:
    lang_c = path.suffix == ".c"
    exe = os.path.join(workdir, "prog")
    src = os.path.join(workdir, "main.c" if lang_c else "main.cpp")
    shutil.copy(path, src)
    cmd = ["gcc", "-std=gnu11", "-O2", src, "-o", exe, "-lm"] if lang_c else \
        ["g++", "-std=gnu++17", "-O2", src, "-o", exe]
    r = subprocess.run(cmd, capture_output=True, timeout=60)
    if r.returncode != 0 and lang_c:
        r = subprocess.run(cmd[:1] + ["-include", "stdbool.h"] + cmd[1:], capture_output=True, timeout=60)
    return exe if r.returncode == 0 else None


def run_oracle(args) -> list[str | None]:
    """Outputs of one ACCEPTED submission on every input (None = failed/timeout)."""
    path, inputs = args
    workdir = tempfile.mkdtemp(prefix="oracle-")
    os.chmod(workdir, 0o777)
    try:
        exe = compile_source(Path(path), workdir)
        if not exe:
            return [None] * len(inputs)
        outs = []
        for i, inp in enumerate(inputs):
            ip = os.path.join(workdir, f"in{i}")
            with open(ip, "w", encoding="utf-8") as f:
                f.write(inp)
            r = run_process([exe], stdin_path=ip, workdir=workdir, timeout_s=LIMITS.time_s,
                            limits=LIMITS, tag=f"o{i}")
            ok = not r["timed_out"] and r["signal"] is None and not r["output_limit"]
            outs.append(r["stdout"] if ok else None)
        return outs
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def tokens(s: str) -> str:
    return " ".join(s.split())


def consensus(outputs: list[str | None]) -> tuple[str | None, int, int]:
    done = [o for o in outputs if o is not None]
    if not done:
        return None, 0, 0
    counts = Counter(tokens(o) for o in done)
    top, k = counts.most_common(1)[0]
    if k >= 2 and k * 3 >= 2 * len(done):
        raw = next(o for o in done if tokens(o) == top)
        lines = [ln.rstrip() for ln in raw.replace("\r\n", "\n").split("\n")]
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines) + "\n", k, len(done)
    return None, k, len(done)


def build_problem(raw_root: Path, problem_id: str, n_oracles: int, seed: int, workers: int) -> dict:
    acc = submissions(raw_root, problem_id, "ACCEPTED")
    rng = random.Random(seed + gen.hash_str(problem_id))
    oracles = rng.sample(acc, min(n_oracles, len(acc)))
    tests = statement_samples(raw_root, problem_id) + gen.plan_for(problem_id, seed)
    inputs = [t["input"] for t in tests]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(run_oracle, [(str(p), inputs) for p in oracles]))
    kept, dropped = [], Counter()
    sample_ok = True
    for i, t in enumerate(tests):
        out, agree, finished = consensus([r[i] for r in results])
        if t["kind"] == "sample":
            if out is None or tokens(out) != tokens(t["statement_output"]):
                sample_ok = False
        if out is None:
            dropped["no_consensus" if finished else "no_oracle_finished"] += 1
            continue
        ref = gen.REFERENCES.get(problem_id)
        ref_checked = False
        if ref is not None:
            if tokens(ref(t["input"])) != tokens(out):
                dropped["accepted_disagree_with_reference"] += 1
                continue
            ref_checked = True
        rec = {"name": f"{t['kind']}-{i:02d}", "kind": t["kind"], "gen_seed": t["gen_seed"],
               "input_sha256": hashlib.sha256(t["input"].encode()).hexdigest(),
               "input": t["input"] if len(t["input"]) <= STORE_LIMIT or t["gen_seed"] is None else None,
               "output": out, "oracle_agree": agree, "oracle_finished": finished,
               "reference_checked": ref_checked}
        kept.append(rec)
    return {"problem_id": problem_id, "generator_version": GENERATOR_VERSION, "seed": seed,
            "oracles": [str(p.relative_to(raw_root)) for p in oracles], "n_accepted": len(acc),
            "sample_check": sample_ok, "tests": kept, "dropped": dict(dropped)}


def load_tests(problem_id: str, out_dir: Path = OUT_DIR) -> list[dict] | None:
    """Tests with inputs restored (regenerated where not stored); None if unusable."""
    p = out_dir / f"{problem_id}.json.gz"
    if not p.exists():
        return None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        data = json.load(f)
    if not data["sample_check"]:
        return None
    out = []
    for t in data["tests"]:
        inp = t["input"]
        if inp is None:
            inp = gen.generate(problem_id, t["kind"], random.Random(t["gen_seed"]))
            if hashlib.sha256(inp.encode()).hexdigest() != t["input_sha256"]:
                raise RuntimeError(f"{problem_id}/{t['name']}: regenerated input differs (generator changed?)")
        out.append({"input": inp, "output": t["output"], "name": t["name"], "kind": t["kind"]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--oracles", type=int, default=7)
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--problems", nargs="*", default=sorted(gen.GENERATORS))
    a = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for pid in a.problems:
        data = build_problem(a.raw_root, pid, a.oracles, a.seed, a.workers)
        with gzip.open(OUT_DIR / f"{pid}.json.gz", "wt", encoding="utf-8", compresslevel=9) as f:
            json.dump(data, f)
        kinds = Counter(t["kind"] for t in data["tests"])
        rows.append((pid, data["n_accepted"], len(data["oracles"]), data["sample_check"],
                     len(data["tests"]), dict(kinds), data["dropped"]))
        print(rows[-1], flush=True)
    lines = ["# PROGPedia oracle tests", "",
             "Generated by `scripts/progpedia_oracle_tests.py`. Do not edit by hand.", "",
             f"Seed `{a.seed}` · generators `{GENERATOR_VERSION}` · up to {a.oracles} ACCEPTED C/C++ oracles per "
             "problem · a test is kept when ≥2 oracles agree and they are ≥2/3 of the oracles that finished · "
             "a problem is usable only if the consensus reproduces the statement's sample outputs. Where a short "
             "independent Python reference exists (6 problems) a test is also dropped when the consensus disagrees "
             "with it — that input lies outside what the original judge tested.", "",
             "| Problem | ACCEPTED C/C++ | Oracles | Samples reproduced | Tests kept | By kind | Dropped |",
             "|---|---:|---:|---|---:|---|---|"]
    for pid, nacc, nor, ok, nt, kinds, dropped in rows:
        lines.append(f"| {pid} | {nacc} | {nor} | {'yes' if ok else '**no — problem unusable**'} | {nt} | "
                     f"{', '.join(f'{k} {v}' for k, v in kinds.items())} | {dropped or ''} |")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
