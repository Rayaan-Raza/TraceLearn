# Do the round-2 agent-written programs transfer to real student code?

Measured on the 324 held-out real rows (20 unseen problems), features static + warnings + semantics, plain
XGBoost (200 trees, depth 4), no abstention, no calibration. Training sets differ only in which rows are used.
Training rows: 314 verified agent-written programs in 83 problems (`stu-s2-*`), the older template mutants,
and the real rows.

| Training rows | Predicted classes on the held-out rows | False alarm on OTHER | Precision when flagged | Misconception recall |
|---|---|---|---|---|
| synth2 only | 11 classes, 283 of 324 flagged | 86% | 8.1% | 22.8% (off-by-one 26%, array bounds 24%) |
| all synthetic | 256 of 324 flagged | 78% | 3.9% | 9.9% |
| real only | OTHER 264, ARRAY_BOUNDS 60 | 4.5% | 80.0% | 47.5% |
| real + synth2 | OTHER 265, ARRAY_BOUNDS 59 | 4.5% | 81.4% | 47.5% |

Reading:

- Adding the programs to the real rows changes nothing on real code: the trees keep the synthetic and the real
  rows apart (the programs are short and uniform; the real ones are long), so real submissions never land in
  the synthetic regions. The held-out predictions are the same two classes as before.
- Trained alone, the programs do carry some signal for the thin classes (off-by-one recall 26%), but they flag
  most real code, so the model is useless on its own.
- The same domain gap is the reason the older template mutants never helped (see `docs/6-nov.md`, sections 12-14).
  The thin classes need either real examples or features that describe the bug itself (an index expression, a
  loop operator, a comparison chain) and not the size and shape of the program.
