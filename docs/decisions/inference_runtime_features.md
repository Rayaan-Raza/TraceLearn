# Decision: how the served model gets its features (week 1)

Owner: Umaima · 8 Nov 2026 · for Rayaan's `MODEL_VARIANT` choice (6-Nov plan §6, Umaima week 1)

## Question

The `full` model was trained with **runtime** features (ASan/UBSan, Valgrind) that come from
`sandbox_runner`. The backend runs student code in its own bubblewrap sandbox, without
sanitizers or Valgrind. Options:

- **(a)** run `sandbox_runner` on every model submission, so the runtime block exists live;
- **(b)** serve a variant that needs no runtime block: `best` (static + warnings + semantics) or
  `common` (static + warnings).

## Decision

**(b): serve `best`, with the warnings computed by one compile using the training flags.**
Runtime features stay off at inference for Iteration 2. `best` is already the default
`MODEL_VARIANT` in `backend/app/config.py`. This confirms it, with the conditions below.

## Evidence

Latency, from `scripts/measure_inference_latency.py` → `reports/inference_latency.json`.
Sample: 40 failing CodeStream C/C++ submissions (seed 20261108), no cache, 2-CPU container.

| Path | p50 | p95 | max |
|---|---:|---:|---:|
| `sandbox_runner` full (warnings, tests twice, ASan/UBSan, Valgrind) | 1.28 s | **17.4 s** | 29.1 s |
| `sandbox_runner` without Valgrind | 0.68 s | 2.05 s | 2.9 s |
| `sandbox_runner` compile + tests + warnings | 0.34 s | 1.31 s | 1.6 s |
| one warnings compile with the training flags (`WARNING_FLAGS`, `-O2 … -c`) | 0.04 s | 1.20 s | 1.2 s |
| backend's current warnings call (`-fsyntax-only -Wall -Wextra`) | 0.01 s | 1.04 s | 1.1 s |
| static + semantics extraction from source | 1 ms | 1 ms | 2 ms |

Gate I10 allows **< 2 s p95 for the whole added path and at most one extra g++ call**.
- Option (a) fails it: full is 17 s p95 because of Valgrind. Even without Valgrind it is about
  2 s, *on top of* the backend's own test run, and it needs a second (sanitizer) compile.
- Option (b) adds about 0.2 s p95. The training-flag warnings compile costs about the same as
  the `-fsyntax-only` call it replaces, and extraction is about 1 ms.

Accuracy, from `scripts/variant_skew_check.py` → `reports/inference_variant_skew.json`
(macro-F1 on the pools' current labels, mostly weak: read these as directions, not accuracy):

| Model / features available | CV (grouped) | dev_gold (45) | test_iid (36) |
|---|---:|---:|---:|
| `full`, every block | 0.725 | 0.643 | 0.731 |
| `full`, no runtime | — | 0.616 | 0.678 |
| `full`, no runtime, no cpg | — | **0.186** | **0.224** |
| `best` | 0.703 | 0.616 | 0.671 |
| `common` | 0.710 | 0.368 | 0.652 |

- Runtime is worth roughly +0.02 to +0.05. Not worth 17 s, and not needed for a first release.
- **`full` must not be served** unless every block it was trained on is computed live with
  parity. Without `cpg` it collapses to about 0.2, a silent train/serve skew.
- `best` matches `full`-without-runtime and needs only the source and one compile.

## Conditions (these make the decision safe)

1. **Warnings must use the training flags.** On 200 sampled submissions, **162 (81%)** get a
   different warning set from the backend's current `-fsyntax-only -Wall -Wextra` call than
   from the training flags. Missing: `-Wunused-result` (137), `-Wconversion` (27),
   `-Wfloat-conversion` (25), `-Wmaybe-uninitialized` (16, which needs `-O2`, so
   `-fsyntax-only` can never produce it), `-Wuninitialized` (8). `best` has 24 warning
   features, so the live path must compile with `sandbox_runner.config.WARNING_FLAGS` (`-c`,
   not `-fsyntax-only`). Rayaan's unmerged branch `feat/plain-model-live-warnings` already does
   this in `backend/app/analysis/model_runner.py`. Keep that, and add warnings to the I1
   parity test.
2. **Same compiler version as training** (g++ 13.3). Pin it in the `Dockerfile`; warning
   counts change across versions.
3. **I1 parity** covers `static`, `warnings` and `semantics` for `best`. No other block is
   needed.

## Revisit when

- the model is evaluated on signed gold and the runtime gain is measured on certain labels; or
- an asynchronous path exists (rule diagnosis first, model block later, blueprint fallback in
  I10). Then `sandbox_runner` without Valgrind (2 s p95) becomes affordable, but only with a
  parity test for the runtime block.
