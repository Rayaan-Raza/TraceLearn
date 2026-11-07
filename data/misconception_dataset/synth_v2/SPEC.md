# Verified student-style programs, round 2 (agent authors)

Goal: many *different* small C++ programs, each with ONE misconception bug that a beginner
really makes, so the model can learn the thin classes from varied code instead of 20 templates.
`scripts/build_synth_v2.py` runs every program; anything that does not verify is dropped, so
write carefully but do not worry about being wrong sometimes.

## What to write

A JSON file with this shape (path given in your task):

    {"problems": [
      {"id": "S2-<AGENT>-01", "title": "short title",
       "statement": "2-4 sentences: what the program reads from stdin and prints",
       "tests": ["stdin text 1", "stdin text 2", "... at least 8 inputs ..."],
       "reference": "<complete correct C++ program>",
       "bugs": [
         {"label": "CPP_OFF_BY_ONE",
          "buggy": "<complete C++ program with the bug>",
          "fixed": "<the SAME program with only the bug removed: must pass every test>",
          "note": "what the student got wrong, one sentence"} ]}
    ]}

- Write 14 problems. Give each problem 3 to 5 bugs of DIFFERENT classes (see the table), one of
  them `CPP_OTHER_ERROR` where it fits (see below).
- `tests` are stdin inputs only. Expected outputs are produced by running `reference`, so the reference
  must be correct, deterministic, finish within 1 second, read stdin and write stdout, no files, no
  randomness, no undefined behaviour. Include edge cases AND at least two inputs large enough to expose
  the bug classes you use (e.g. values near 2^31 for overflow, array sizes near the limit, n = 0 or 1).
- `fixed` must differ from `buggy` by the bug only (at most 4 changed lines) and must pass all tests.
  `buggy` must compile and fail at least one test (wrong output, crash or timeout).
- The class must be the cause of the FIRST failing test: if only that were fixed, the first failing test
  would pass. One bug per program; do not stack bugs.
- Student style: beginner code, mixed styles (`cin/cout`, `scanf/printf`, `vector`, plain arrays, helper
  functions, `while` as well as `for`), short variable names such as `n, i, j, sum, cnt, a`, a few comments
  at most. Not textbook-clean and not deliberately weird. Programs are 8 to 40 lines.
- Make the 14 problems genuinely different from each other (different tasks, data shapes and structure);
  do not write 14 variations of "sum the numbers". Do not copy the example programs under
  `data/cpp_diagnostics` and do not open them.

## Classes (label the cause of the first failing test)

| Label | The bug |
|---|---|
| CPP_LOOP_BOUNDARY | wrong loop comparison operator: `<=` where `<` is right or the reverse (changing only the operator fixes it) |
| CPP_OFF_BY_ONE | an index, count or starting value is off by one (`a[i+1]`, start at 1 instead of 0, `n` instead of `n-1`, `size()` vs `size()-1`) with the loop operator right |
| CPP_ARRAY_BOUNDS | access far outside an array/vector, or a fixed array too small for the input (e.g. `int a[10]` but n up to 1000), or an index taken from input without a check |
| CPP_RANGE_CHECK | a range or condition test written wrongly: `0 < x < 10`, `x > 1 && x < 10` where `>=` is meant, `||` for `&&`, comparing against the wrong bound |
| CPP_ASSIGN_VS_COMPARE | `=` written where `==` is meant inside a condition |
| CPP_STALE_EXIT | a loop or search that keeps a stale value or stops too early: `break`/`return` inside the loop at the wrong point, a flag never reset, using the first match when the last is needed |
| CPP_WRONG_LOOP_DIR | a loop that counts the wrong way (`i--` where `i++`, or the reverse, or iterating from the wrong end) |
| CPP_MISSING_BASE_CASE | a recursive function with no (or an unreachable) stopping case, so it recurses forever or crashes |
| CPP_UNINITIALIZED_VAR | a variable declared and used before it is set on some path (a sum, counter, min or max not initialised) |
| CPP_INT_OVERFLOW | a value outgrows `int` (products, sums, factorials, powers): small tests pass, large ones fail |
| CPP_OTHER_ERROR | a bug that fits none of the above: wrong formula, a missed special case, wrong output format, wrong condition meaning, wrong sort order. Use it for contrast: logic mistakes are the most common real failure |

## Rules

- Only complete programs with `int main`. Standard headers only.
- Do not read any other file in the repository. Do not look at other authors' files in `synth_v2`.
- Write the JSON file with a proper JSON string escape for newlines (`\n`) and quotes. Check that it parses.
