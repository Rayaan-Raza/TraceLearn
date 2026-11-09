"""Blind labelling pool from real Project CodeNet C++ submissions (AtCoder beginner problems).

    wsl python3 scripts/build_codenet_pool.py --raw-root /mnt/g/TraceLearn/Datasets_RAW

The raw CodeNet copy has code but no verdicts and no tests, so this derives both:

1. Tests: the statement's sample cases plus seeded generated inputs (edge values first). The
   expected output comes from a reference solution per problem (`REFERENCES`), which must
   reproduce every sample output of the statement. The submissions' majority output is
   reported as a cross-check only: on p02742 it is wrong, because most submissions miss the
   one-row board.
2. Failing submissions: compile, fail at least one derived test, and are not timeout-only.

Items are de-duplicated by normalised code, capped per problem, shuffled with a fixed seed and
written as shards (statement, first failing test, expected, observed, code) to the gitignored
cache. Nothing from a rule or the model is shown. Tests go to `oracle_tests/codenet/`.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sandbox_runner import RunConfig, run_many  # noqa: E402

DS = ROOT / "data" / "misconception_dataset"
OUT = DS / "cache" / "cn_pool"
TESTS = DS / "oracle_tests" / "codenet"
SEED = 20261109
SHARD = 60
SAMPLE_PER_PROBLEM = 450
CAP_PER_PROBLEM = 70
N_GENERATED = 16
# Whole problems that never reach training: an unseen-problem test drawn from the same source.
HELDOUT_PROBLEMS = ("p02766", "p03803")
COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)


def norm_key(code: str) -> str:
    return hashlib.md5(re.sub(r"\s+", "", COMMENT.sub("", code)).encode()).hexdigest()


def clip(text: str, n: int) -> str:
    text = (text or "").replace("\r\n", "\n").strip("\n")
    return text if len(text) <= n else text[:n] + "\n...[cut]"


def canon(out: str) -> str:
    return "\n".join(line.rstrip() for line in (out or "").replace("\r\n", "\n").strip().split("\n"))


# ---------------------------------------------------------------- input generators
# Each returns one input string. Edge values are listed first, then random values within the
# statement's constraints.

def g_p02742(r, i):  # bishop, 1 <= H, W <= 1e9
    edge = [(1, 1), (1, 7), (7, 1), (2, 2), (3, 3), (10**9, 10**9), (10**9, 1), (999999999, 999999999)]
    h, w = edge[i] if i < len(edge) else (r.randint(1, 10**9), r.randint(1, 10**9))
    return f"{h} {w}\n"


def g_p02594(r, i):  # -40 <= X <= 40
    edge = [30, 29, 31, -40, 40, 0]
    return f"{edge[i] if i < len(edge) else r.randint(-40, 40)}\n"


def g_p02766(r, i):  # 1 <= N <= 1e9, 2 <= K <= 10
    edge = [(1, 2), (2, 2), (8, 2), (7, 2), (10, 10), (9, 10), (10**9, 10), (10**9, 2), (100, 10)]
    n, k = edge[i] if i < len(edge) else (r.randint(1, 10**9), r.randint(2, 10))
    return f"{n} {k}\n"


def g_p02981(r, i):  # 1 <= N <= 20, 1 <= A, B <= 50
    edge = [(1, 1, 1), (20, 50, 50), (4, 2, 8), (4, 2, 7), (4, 2, 9)]
    n, a, b = edge[i] if i < len(edge) else (r.randint(1, 20), r.randint(1, 50), r.randint(1, 50))
    return f"{n} {a} {b}\n"


def g_p02708(r, i):  # 1 <= N <= 2e5, 1 <= K <= N+1
    edge = [(1, 1), (1, 2), (3, 2), (3, 4), (200000, 1), (200000, 200001), (141421, 35623)]
    if i < len(edge):
        n, k = edge[i]
    else:
        n = r.choice([r.randint(1, 50), r.randint(1, 200000)])
        k = r.randint(1, n + 1)
    return f"{n} {k}\n"


def g_p02887(r, i):  # 1 <= N <= 1e5, lowercase S
    edge = ["a", "aa", "ab", "aaaaa", "abababab", "aabbccaabb"]
    s = edge[i] if i < len(edge) else "".join(r.choice("ab" if r.random() < .5 else "abcz") for _ in range(r.randint(1, 60)))
    return f"{len(s)}\n{s}\n"


def g_p03632(r, i):  # 0 <= A < B <= 100, 0 <= C < D <= 100
    edge = [(0, 75, 25, 100), (0, 33, 66, 99), (10, 90, 20, 80), (0, 50, 50, 100), (0, 1, 0, 1), (20, 30, 10, 20)]
    if i < len(edge):
        a, b, c, d = edge[i]
    else:
        a, b = sorted(r.sample(range(101), 2))
        c, d = sorted(r.sample(range(101), 2))
    return f"{a} {b} {c} {d}\n"


def g_p03012(r, i):  # 2 <= N <= 100, 1 <= W_i <= 100
    edge = [[1, 2, 3], [1, 3, 1, 1], [100, 1], [1, 100], [5, 5], [1] * 100]
    w = edge[i] if i < len(edge) else [r.randint(1, 100) for _ in range(r.randint(2, 100))]
    return f"{len(w)}\n{' '.join(map(str, w))}\n"


def g_p03803(r, i):  # 1 <= A, B <= 13
    edge = [(1, 13), (13, 1), (1, 1), (2, 1), (1, 2), (13, 12), (8, 8)]
    a, b = edge[i] if i < len(edge) else (r.randint(1, 13), r.randint(1, 13))
    return f"{a} {b}\n"


def g_p02607(r, i):  # 1 <= N, a_i <= 100
    edge = [[1], [2], [1, 3, 4, 5, 7], [2, 4, 6], [1] * 100]
    a = edge[i] if i < len(edge) else [r.randint(1, 100) for _ in range(r.randint(1, 100))]
    return f"{len(a)}\n{' '.join(map(str, a))}\n"


def g_p02633(r, i):  # 1 <= X <= 179
    edge = [90, 1, 179, 120, 45, 60, 7]
    return f"{edge[i] if i < len(edge) else r.randint(1, 179)}\n"


GENERATORS = {name[2:]: fn for name, fn in globals().items() if name.startswith("g_p")}


# ---------------------------------------------------------------- reference solutions
# The expected output of every derived test comes from these, written from the statements.
# The submissions' majority is only a cross-check: on p02742 most submissions miss the
# one-row board (the bishop cannot move, the answer is 1), so the majority answer is wrong
# there. Every reference reproduces the statement's sample outputs (checked below).

def _ints(s):
    return list(map(int, s.split()))


def r_p02742(s):
    h, w = _ints(s)
    return str(1 if h == 1 or w == 1 else (h * w + 1) // 2)


def r_p02594(s):
    return "Yes" if int(s) >= 30 else "No"


def r_p02766(s):
    n, k = _ints(s)
    c = 0
    while n:
        n //= k
        c += 1
    return str(c)


def r_p02981(s):
    n, a, b = _ints(s)
    return str(min(n * a, b))


def r_p02708(s):
    n, k = _ints(s)
    return str(sum(m * (2 * n - m + 1) // 2 - m * (m - 1) // 2 + 1 for m in range(k, n + 2)) % (10**9 + 7))


def r_p02887(s):
    t = s.split()[1]
    return str(1 + sum(t[i] != t[i - 1] for i in range(1, len(t))))


def r_p03632(s):
    a, b, c, d = _ints(s)
    return str(max(0, min(b, d) - max(a, c)))


def r_p03012(s):
    v = _ints(s)
    w, total, pre, best = v[1:], sum(v[1:]), 0, None
    for t in range(v[0] - 1):
        pre += w[t]
        best = abs(total - 2 * pre) if best is None else min(best, abs(total - 2 * pre))
    return str(best)


def r_p03803(s):
    a, b = (14 if x == 1 else x for x in _ints(s))
    return "Alice" if a > b else "Bob" if b > a else "Draw"


def r_p02607(s):
    a = _ints(s)[1:]
    return str(sum(1 for i, x in enumerate(a) if i % 2 == 0 and x % 2 == 1))


def r_p02633(s):
    import math
    return str(360 // math.gcd(int(s), 360))


REFERENCES = {name[2:]: fn for name, fn in globals().items() if name.startswith("r_p")}


def samples(raw_root: Path, pid: str) -> list[dict]:
    f = raw_root / "Project_CodeNet" / "Project_CodeNet" / "problem_descriptions" / f"{pid}.html"
    text = f.read_text(encoding="utf-8", errors="replace")
    pres = [html.unescape(re.sub(r"<[^>]+>", "", p)) for p in re.findall(r"(?is)<pre[^>]*>(.*?)</pre>", text)]
    heads = re.findall(r"(?i)Sample (Input|Output)\s*\d+", text)
    # AtCoder pages carry the English statement after the Japanese one; the samples are the
    # trailing <pre> blocks in input/output pairs.
    n = len(heads) // 2 if heads else 0
    blocks = pres[-2 * n:] if n else []
    return [{"input": blocks[2 * k].strip() + "\n", "output": blocks[2 * k + 1].strip()} for k in range(n)]


def statement(raw_root: Path, pid: str) -> str:
    f = raw_root / "Project_CodeNet" / "Project_CodeNet" / "problem_descriptions" / f"{pid}.html"
    text = f.read_text(encoding="utf-8", errors="replace")
    i = text.find("Problem Statement")
    body = text[i:] if i >= 0 else text
    j = body.find("Sample Input")
    body = body[:j] if j > 0 else body
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", html.unescape(re.sub(r"<[^>]+>", " ", body)))).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    base = a.raw_root / "Project_CodeNet" / "Project_CodeNet" / "data"
    rng = random.Random(SEED)
    cfg = RunConfig(warnings_pass=False, sanitizer_pass=False, valgrind_pass=False, double_run=False,
                    stop_after_timeouts=2, keep_stdout_bytes=600)
    cache = str(DS / "cache" / "codenet_exec" / "runs")
    TESTS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    items, stmts = [], {}
    for pid, gen in sorted(GENERATORS.items()):
        files = sorted((base / pid / "C++").glob("*.cpp"))
        rng.shuffle(files)
        subs, seen = [], set()
        for f in files:
            code = f.read_text(encoding="utf-8", errors="replace")
            k = norm_key(code)
            if k in seen or len(code) > 6000:
                continue
            seen.add(k)
            subs.append({"source_record_id": f"{pid}/C++/{f.name}", "code": code, "sha": k})
            if len(subs) >= SAMPLE_PER_PROBLEM:
                break
        samp = samples(a.raw_root, pid)
        gr = random.Random(f"{SEED}-{pid}")
        inputs = [s["input"] for s in samp] + [gen(gr, i) for i in range(N_GENERATED)]
        probe = [{"input": x, "output": ""} for x in inputs]
        runs = list(run_many([(s["code"], "cpp", probe) for s in subs], cfg, workers=a.workers, cache_dir=cache))
        compiled = [(s, r) for s, r in zip(subs, runs) if (r.get("compile") or {}).get("ok")]
        outs = []
        for s, r in compiled:
            by = {x.get("idx"): x for x in (r.get("tests") or {}).get("results", [])}
            outs.append([canon(by[i].get("stdout_head", "")) if i in by and by[i].get("status") not in ("timeout", "crash", "output_limit", "skipped", None)
                         else None for i in range(len(inputs))])
        expected = [canon(REFERENCES[pid](x)) for x in inputs]
        bad_samples = [k for k, s in enumerate(samp) if expected[k] != canon(s["output"])]
        if not samp or bad_samples:
            print(f"{pid}: DROPPED (samples {len(samp)}, reference disagrees on {bad_samples})", flush=True)
            continue
        majority_wrong = []
        for i in range(len(inputs)):
            votes = Counter(o[i] for o in outs if o[i] is not None)
            top = votes.most_common(1)[0][0] if votes else None
            if top != expected[i]:
                majority_wrong.append(inputs[i].strip()[:30])
        if majority_wrong:
            print(f"{pid}: the majority output is wrong on {len(majority_wrong)} input(s): {majority_wrong}", flush=True)
        tests = [{"input": x, "output": e} for x, e in zip(inputs, expected) if e is not None]
        with gzip.open(TESTS / f"{pid}.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(tests, fh)
        stmts[pid] = statement(a.raw_root, pid)
        keep_idx = [i for i, e in enumerate(expected) if e is not None]
        failing = []
        for (s, r), o in zip(compiled, outs):
            res = {x.get("idx"): x for x in (r.get("tests") or {}).get("results", [])}
            fails = [j for j, i in enumerate(keep_idx) if o[i] != expected[i]]
            if not fails:
                continue
            statuses = {(res.get(keep_idx[j]) or {}).get("status") for j in fails}
            if statuses <= {"timeout", None}:
                continue          # timeout-only: not a clean failing case
            first = fails[0]
            got = res.get(keep_idx[first]) or {}
            failing.append({**s, "problem_id": pid, "first_failed": first, "tests_total": len(tests),
                            "tests_passed": len(tests) - len(fails), "observed": got.get("stdout_head", ""),
                            "observed_status": got.get("status"), "rc": got.get("rc")})
        rng.shuffle(failing)
        print(f"{pid}: {len(subs)} sampled, {len(compiled)} compile, {len(tests)} tests, {len(failing)} failing "
              f"-> {min(len(failing), CAP_PER_PROBLEM)} kept", flush=True)
        items += failing[:CAP_PER_PROBLEM]
    rng.shuffle(items)
    manifest, blocks = [], []
    for n, s in enumerate(items, 1):
        item = f"CN-{n:04d}"
        tests = json.load(gzip.open(TESTS / f"{s['problem_id']}.json.gz", "rt", encoding="utf-8"))
        case = tests[s["first_failed"]]
        manifest.append({"item_id": item, "problem_id": s["problem_id"], "source_record_id": s["source_record_id"],
                         "sha": s["sha"], "lang": "cpp", "tests_passed": s["tests_passed"], "tests_total": s["tests_total"],
                         "group": "heldout" if s["problem_id"] in HELDOUT_PROBLEMS else "train"})
        blocks.append(
            f"===== {item} | {s['problem_id']} | derived tests {s['tests_passed']}/{s['tests_total']}\n"
            f"--- first failing test input:\n{clip(case['input'], 220)}\n"
            f"--- expected output:\n{clip(case['output'], 160)}\n"
            f"--- observed output (status {s['observed_status']}, rc {s['rc']}):\n{clip(s['observed'], 160)}\n"
            f"--- code (cpp):\n{clip(s['code'], 2600)}\n")
        s["item_id"] = item
    for i in range(0, len(blocks), SHARD):
        (OUT / f"shard_{i // SHARD + 1:02d}.txt").write_text("\n".join(blocks[i:i + SHARD]), encoding="utf-8", newline="\n")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8", newline="\n")
    (OUT / "statements.md").write_text("\n".join(f"## {p}\n{clip(t, 1800)}\n" for p, t in sorted(stmts.items())),
                                       encoding="utf-8", newline="\n")
    with (OUT / "items.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for s in items:
            fh.write(json.dumps(s) + "\n")
    print(f"{len(manifest)} failing items in {-(-len(blocks) // SHARD)} shards -> {OUT}; "
          f"heldout {sum(m['group'] == 'heldout' for m in manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
