# sandbox_runner

The shared C/C++ execution harness for the misconception dataset
(Master Plan v4.1 §5 and §9.2-U0). Owner: **Umaima (Lane B)**. Every lane imports
it; nobody re-implements execution.

```python
from sandbox_runner import run_submission, RunConfig

res = run_submission(code, "cpp", [{"input": "3\n", "output": "6\n"}])
res["branch"]                       # compile_error | all_pass | timeout_only | failing
res["tests"]["passed"], res["tests"]["total"], res["tests"]["first_failed"]
res["warnings"]["count_by_flag"]    # {"-Wparentheses": 1, ...}
res["runtime"]["sanitizer"]["reports"]   # ASan / UBSan reports with lines
res["runtime"]["valgrind"]["uninit"]     # Valgrind memcheck uninitialised-value use
```

Bulk runs: `run_many(jobs, workers=N, cache_dir=...)` with `jobs = [(code, lang, tests), ...]`.
CLI: `python -m sandbox_runner.cli run main.cpp --tests tests.json` and
`python -m sandbox_runner.cli env`.

## What one call does

| Step | Build | Flags | Per-test limit |
|---|---|---|---|
| Warnings + test binary | `g++ -std=c++17` / `gcc -std=c11` | `-O2 -Wall -Wextra -Wmaybe-uninitialized -Wparentheses -Warray-bounds -Wshadow -Wconversion` | 2 s |
| Tests | the binary above | stdin from file, stdout to a capped file | 2 s, run twice (determinism) |
| Sanitizer pass | separate build | `-O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined` | 6 s (×3) |
| Valgrind pass | separate build | `-O0 -g`, `memcheck --track-origins=yes` | 30 s (×15), first failing test |

Valgrind memcheck is the default uninitialised-value detector (clang MSan is
optional and not used: it needs an instrumented libc++).

## Result fields

* `compile` — `ok`, `rc`, `errors[]` (line, message), `stderr_head`.
* `warnings` — `count_by_flag`, `items[]` (line, col, message, flag). System-header diagnostics are dropped.
* `tests` — `total` (flaky tests excluded), `passed` (exact up to trailing whitespace),
  `passed_lenient` (+ presentation), `status_counts`, `flaky[]`, `first_failed`,
  `results[]` with `status` ∈ pass / presentation / wrong / timeout / crash /
  output_limit / nonzero_exit / skipped, and a `diff` block for failures:
  `numeric_deltas`, `all_deltas_pm1`, `reversed_tokens`, `same_multiset`,
  `prefix_tokens`, `is_prefix_of_expected`, `empty_output`, …
* `runtime` — `any_crash`, `any_timeout`, `signals`, `stack_overflow`,
  `sanitizer` (`reports[]`, `kinds`, `first_report`; ASan reports carry
  `bytes_past_end` / `elements_past_end`, which split class 2 from class 3),
  `valgrind` (`kinds`, `uninit`, `error_count`).
* `branch` — the deterministic pre-branch of §1/§12. `timeout_only` means a
  timeout with no crash and no sanitizer report.
* `null` means "not measured", never 0.

## Isolation

* **docker backend** (`backend="docker"`, image from `sandbox_runner/docker/Dockerfile`):
  `--network none`, `--read-only`, tmpfs `/tmp`, user 65534, `--pids-limit 64`,
  memory limit, `--cpus 1`, `--cap-drop ALL`, `no-new-privileges`. This is the
  configuration the bulk run and G0b require.
* **local backend** (default, used for development and CI): own process group
  killed on timeout, RLIMIT_CPU/STACK(64 MB)/FSIZE(output cap)/AS(512 MB for
  plain builds), uid 65534 when started as root, empty network namespace via
  `unshare` when the host allows it. `python -m sandbox_runner.cli env` prints
  what the host achieves; `scripts/sandbox_manifest.py` records it.

## Caching and speed

Results are cached by SHA-256 of (language, code, tests, config fingerprint,
toolchain). `<bits/stdc++.h>` is precompiled once per flag set (`pch.py`) —
speed only, the result is identical.

## Known behaviour worth knowing

* At `-O2` gcc may turn an unguarded recursion into an endless loop. The test
  then times out, but the `-O1` sanitizer build still reports `stack-overflow`,
  so `runtime.stack_overflow` is true and the branch is `failing`.
* An empty infinite loop is undefined behaviour in C++ and may be optimised away.
