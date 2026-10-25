"""Seeded input generators for the PROGPedia problems (oracle tests).

PROGPedia ships verdicts but no tests. `progpedia_oracle_tests.py` builds tests
by generating inputs here and taking the expected output from agreeing
ACCEPTED submissions. Each generator follows its problem's statement:
input format, value ranges and the guarantees the statement promises (e.g. a
coverable segment, a connected graph, an answer below 2^63).

``generate(problem, kind, rng)`` returns one input string. ``kind`` is one of
``small``, ``medium``, ``edge`` or ``large``. ``large`` inputs are sized so a
correct O(n log n) program finishes well under the 2 s limit, and are where
overflow-prone answers (inversions, pyramid paths) exceed 2^31.
"""

from __future__ import annotations

import random
from typing import Callable

KINDS = ("small", "medium", "edge", "large")


def _lines(*rows) -> str:
    return "\n".join(" ".join(str(x) for x in r) if isinstance(r, (list, tuple)) else str(r)
                     for r in rows) + "\n"


def _connected_edges(rng: random.Random, n: int, extra: int) -> list[tuple[int, int]]:
    """Random spanning tree plus ``extra`` distinct non-tree edges (1-based)."""
    order = list(range(1, n + 1))
    rng.shuffle(order)
    edges = set()
    for i in range(1, n):
        a, b = order[i], order[rng.randrange(i)]
        edges.add((min(a, b), max(a, b)))
    tries = 0
    while len(edges) < n - 1 + extra and tries < extra * 20 + 100:
        tries += 1
        a, b = rng.sample(range(1, n + 1), 2) if n > 1 else (1, 1)
        if a != b:
            edges.add((min(a, b), max(a, b)))
    out = list(edges)
    rng.shuffle(out)
    return [(a, b) if rng.random() < 0.5 else (b, a) for a, b in out]


# --------------------------------------------------------------- problems


def p0006(rng: random.Random, kind: str) -> str:
    """Messy Cicadas: walk over <=30 distinct places (<10000), final place unique, ends with 0."""
    k = {"small": 4, "medium": 12, "edge": 2, "large": 30}[kind]
    places = rng.sample(range(1, 10000), k)
    final = places[-1]
    pool = places[:-1] or [final]
    length = {"small": 6, "medium": 40, "edge": 3, "large": 400}[kind]
    walk = [rng.choice(pool) for _ in range(max(1, length - 1))] if pool != [final] else []
    if kind == "edge":
        walk = [pool[0], pool[0]] if pool != [final] else []
    return _lines(*walk, final, 0)


def p0016(rng: random.Random, kind: str) -> str:
    """Alphabet Soup: two capital words (<=20 letters), first <= second."""
    alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[: {"small": 3, "medium": 6, "edge": 2, "large": 26}[kind]]
    n1 = rng.randint(1, 20)
    w1 = "".join(rng.choice(alpha) for _ in range(n1))
    mode = rng.random()
    if kind == "edge" and mode < 0.5:
        w2 = w1  # equal words -> Nenhum
    elif mode < 0.3:
        w2 = (w1 + "".join(rng.choice(alpha) for _ in range(rng.randint(1, 20 - n1 + 0))))[:20] \
            if n1 < 20 else w1  # proper prefix -> Nenhum
    else:
        cut = rng.randint(0, n1 - 1)
        w2 = w1[:cut] + "".join(rng.choice(alpha) for _ in range(rng.randint(1, 20 - cut)))
    a, b = sorted([w1, w2])
    return _lines(a, b)


def p0021(rng: random.Random, kind: str) -> str:
    """Order: widest-length path with width/height intervals; ids not consecutive; ends -1."""
    n = {"small": 5, "medium": 15, "edge": 2, "large": 60}[kind]
    ids = rng.sample(range(1, 200), n)
    wmin, lmin, hmin = rng.randint(10, 25), rng.randint(10, 25), rng.randint(5, 20)
    wmax, lmax = wmin + rng.randint(0, 15), lmin + rng.randint(5, 25)
    o, d = rng.sample(ids, 2)
    m = {"small": 7, "medium": 30, "edge": 1, "large": 200}[kind]
    rows = [(wmin, wmax, lmin, lmax, hmin), (o, d)]
    for _ in range(m):
        a, b = rng.sample(ids, 2)
        rows.append((a, b, rng.randint(5, 45), rng.randint(5, 55), rng.randint(5, 50)))
    if kind == "edge":
        rows[-1] = (o, d, wmax, lmax, hmin + 5)
    return _lines(*rows, -1)


def p0034(rng: random.Random, kind: str) -> str:
    """Sorting Numbers: N (1..1e5), positive ints < 1e6."""
    n = {"small": 8, "medium": 500, "edge": 1, "large": 20000}[kind]
    vals = [rng.randint(1, 999999) for _ in range(n)]
    if kind == "medium":
        vals = [rng.randint(1, 20) for _ in range(n)]  # many repeats
    return _lines(n, vals)


def p0035(rng: random.Random, kind: str) -> str:
    """Inversions: N (1..1e5), positive ints < 1e6. Large = reversed run, ~5e9 inversions (> 2^31)."""
    n = {"small": 8, "medium": 2000, "edge": 1, "large": 100000}[kind]
    if kind == "large":
        vals = sorted((rng.randint(1, 999999) for _ in range(n)), reverse=True)
    else:
        vals = [rng.randint(1, 999999 if kind != "small" else 9) for _ in range(n)]
    return _lines(n, vals)


def p0039(rng: random.Random, kind: str) -> str:
    """Closest Sums: N (2..1000) set, P (1..1000) queries, values 1..1e6."""
    n = {"small": 5, "medium": 100, "edge": 2, "large": 1000}[kind]
    p = {"small": 4, "medium": 100, "edge": 2, "large": 1000}[kind]
    hi = {"small": 30, "medium": 1000, "edge": 1000000, "large": 1000000}[kind]
    s = [rng.randint(1, hi) for _ in range(n)]
    q = [rng.randint(1, min(1000000, 2 * hi)) for _ in range(p)]
    if kind == "edge":
        q = [1, 1000000]
    return _lines(n, s, p, q)


def p0042(rng: random.Random, kind: str) -> str:
    """Minimum Coverage: M (1..1e6), N (1..1000) segments [L,R] in 0..1e6; always coverable."""
    m = {"small": 10, "medium": 1000, "edge": 1, "large": 1000000}[kind]
    n_target = {"small": 6, "medium": 60, "edge": 1, "large": 1000}[kind]
    segs = []
    pos = 0
    while pos < m and len(segs) < n_target:
        left = max(0, pos - rng.randint(0, max(1, m // 20)))
        right = min(1000000, pos + rng.randint(1, max(1, m // 5)))
        segs.append((left, right))
        pos = right
    if pos < m:
        segs.append((max(0, pos - 1), m))
    while len(segs) < n_target:
        a = rng.randint(0, m)
        segs.append((a, min(1000000, a + rng.randint(0, max(1, m // 4)))))
    rng.shuffle(segs)
    return _lines(m, len(segs), *segs)


def p0043(rng: random.Random, kind: str) -> str:
    """The Shoemaker: N (1..1000) orders, D and M in 1..1000 (small values force ratio ties)."""
    n = {"small": 5, "medium": 100, "edge": 1, "large": 1000}[kind]
    hi = {"small": 4, "medium": 20, "edge": 1000, "large": 1000}[kind]
    rows = [(rng.randint(1, hi), rng.randint(1, hi)) for _ in range(n)]
    return _lines(n, *rows)


def p0045(rng: random.Random, kind: str) -> str:
    """Pyramids: N layers, D missing stones (C,P). Answers stay below 2^63 (N <= 58);
    large pyramids (N >= 40) have answers above 2^31."""
    n = {"small": 5, "medium": 20, "edge": 1, "large": 58}[kind]
    cells = [(c, p) for c in range(1, n + 1) for p in range(1, n - (c - 1) + 1)]
    d = {"small": 3, "medium": 30, "edge": 0, "large": rng.randint(0, 6)}[kind]
    if kind == "large":
        cells = [x for x in cells if x[0] > 1]  # keep the answer large
    miss = rng.sample(cells, min(d, len(cells)))
    return _lines(n, len(miss), *miss)


def p0048(rng: random.Random, kind: str) -> str:
    """Electronic Circuit Networks: N (1..100) points, L links -> number of components."""
    n = {"small": 8, "medium": 50, "edge": 1, "large": 100}[kind]
    links = {"small": 5, "medium": 40, "edge": 0, "large": 150}[kind]
    rows = []
    for _ in range(links):
        a = rng.randint(1, n)
        b = rng.randint(1, n)
        while n > 1 and b == a:
            b = rng.randint(1, n)
        rows.append((a, b))
    return _lines(n, len(rows), *rows)


def p0053(rng: random.Random, kind: str) -> str:
    """Biological network: connected undirected graph, N <= 1500, E <= 5000, no repeated edges."""
    n = {"small": 6, "medium": 120, "edge": 2, "large": 1500}[kind]
    extra = {"small": 3, "medium": 150, "edge": 0, "large": 5000 - 1499}[kind]
    edges = _connected_edges(rng, n, extra)
    return _lines(n, len(edges), *edges)


def p0056(rng: random.Random, kind: str) -> str:
    """Freckles: N (2..100) points with coordinates 0..1000 (one decimal, like the sample)."""
    n = {"small": 4, "medium": 30, "edge": 2, "large": 100}[kind]
    pts = [(f"{rng.randint(0, 1000)}.0", f"{rng.randint(0, 1000)}.0") for _ in range(n)]
    return _lines(n, *pts)


GENERATORS: dict[str, Callable[[random.Random, str], str]] = {
    "tl-progpedia-00000006": p0006,
    "tl-progpedia-00000016": p0016,
    "tl-progpedia-00000021": p0021,
    "tl-progpedia-00000034": p0034,
    "tl-progpedia-00000035": p0035,
    "tl-progpedia-00000039": p0039,
    "tl-progpedia-00000042": p0042,
    "tl-progpedia-00000043": p0043,
    "tl-progpedia-00000045": p0045,
    "tl-progpedia-00000048": p0048,
    "tl-progpedia-00000053": p0053,
    "tl-progpedia-00000056": p0056,
}

# How many generated inputs of each kind every problem gets.
PLAN = {"small": 4, "medium": 3, "edge": 2, "large": 1}


def generate(problem_id: str, kind: str, rng: random.Random) -> str:
    return GENERATORS[problem_id](rng, kind)


def plan_for(problem_id: str, seed: int) -> list[dict]:
    """Deterministic list of {kind, seed, input} for one problem."""
    out = []
    for kind, count in PLAN.items():
        for i in range(count):
            s = (seed * 1_000_003 + hash_str(problem_id) * 97 + KINDS.index(kind) * 13 + i) % (2**31)
            out.append({"kind": kind, "gen_seed": s, "input": generate(problem_id, kind, random.Random(s))})
    return out


def hash_str(s: str) -> int:
    """Stable string hash (Python's hash() is salted per process)."""
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) % (2**31)
    return h


# ------------------------------------------------------- reference solvers
# Independent Python solutions for the problems where one is short. The oracle
# builder drops any test where agreeing ACCEPTED submissions disagree with the
# reference: such an input lies outside what the original judge tested (e.g.
# ACCEPTED Inversions programs that overflow an int at N = 100000).


def _ints(s: str) -> list[int]:
    return [int(x) for x in s.split()]


def r0016(inp: str) -> str:
    a, b = inp.split()[:2]
    for x, y in zip(a, b):
        if x != y:
            return f"{x}{y}\n"
    return "Nenhum\n"


def r0034(inp: str) -> str:
    v = _ints(inp)
    return " ".join(map(str, sorted(v[1:1 + v[0]]))) + "\n"


def r0035(inp: str) -> str:
    v = _ints(inp)
    a = v[1:1 + v[0]]

    def sort(xs):
        if len(xs) <= 1:
            return xs, 0
        m = len(xs) // 2
        left, x = sort(xs[:m])
        right, y = sort(xs[m:])
        out, i, j, inv = [], 0, 0, x + y
        while i < len(left) and j < len(right):
            if right[j] < left[i]:
                out.append(right[j])
                inv += len(left) - i
                j += 1
            else:
                out.append(left[i])
                i += 1
        return out + left[i:] + right[j:], inv
    return f"{sort(a)[1]}\n"


def r0045(inp: str) -> str:
    v = _ints(inp)
    n, d = v[0], v[1]
    bad = {(v[2 + 2 * i], v[3 + 2 * i]) for i in range(d)}
    row = [0 if (1, p) in bad else 1 for p in range(1, n + 1)]
    for c in range(2, n + 1):
        row = [0 if (c, p) in bad else row[p - 1] + row[p] for p in range(1, n - c + 2)]
    return f"{row[0]}\n"


def r0048(inp: str) -> str:
    v = _ints(inp)
    n, m = v[0], v[1]
    parent = list(range(n + 1))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i in range(m):
        a, b = v[2 + 2 * i], v[3 + 2 * i]
        parent[find(a)] = find(b)
    return f"{len({find(x) for x in range(1, n + 1)})}\n"


def r0039(inp: str) -> str:
    v = _ints(inp)
    n = v[0]
    s = v[1:1 + n]
    p = v[1 + n]
    qs = v[2 + n:2 + n + p]
    sums = sorted({s[i] + s[j] for i in range(n) for j in range(i + 1, n)})
    import bisect
    out = []
    for q in qs:
        k = bisect.bisect_left(sums, q)
        cands = [x for x in (sums[k - 1] if k > 0 else None, sums[k] if k < len(sums) else None) if x is not None]
        best = min(abs(x - q) for x in cands)
        out.append(" ".join(str(x) for x in sorted(set(cands)) if abs(x - q) == best))
    return "\n".join(out) + "\n"


REFERENCES: dict[str, Callable[[str], str]] = {
    "tl-progpedia-00000016": r0016,
    "tl-progpedia-00000034": r0034,
    "tl-progpedia-00000035": r0035,
    "tl-progpedia-00000039": r0039,
    "tl-progpedia-00000045": r0045,
    "tl-progpedia-00000048": r0048,
}
