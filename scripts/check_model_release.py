"""Release gate for the misconception classifier: which serving mode is it cleared for?

    python scripts/check_model_release.py

Reads the frozen reports; changes nothing. Prints each gate and the verdict.

  shadow  (run, store, change nothing): needs S1-S3.
  on      (the model's output joins the diagnosis): needs S1-S3 and P1-P4.

S1 the served model files match the golden fixture and the training metrics;
S2 false alarm on OTHER_ERROR is at most 0.30 on every blind set;
S3 backend and model tests are green (checked by CI, not here).
P1 precision when flagged is at least 0.80 on a set with at least 30 misconceptions;
P2 misconception recall is at least 0.50 on that same set;
P3 the labels behind P1/P2 were made by independent people, not the model-assisted reviewer;
P4 the backend supplies compiler-warning counts (the model was trained with them).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DS = Path(__file__).resolve().parents[1] / "data" / "misconception_dataset"
ROOT = Path(__file__).resolve().parents[1]


def blind(name: str):
    path = DS / "reports" / f"blind_{name}_eval.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main() -> int:
    gates: list[tuple[str, bool, str]] = []
    golden = json.loads((ROOT / "backend" / "tests" / "fixtures" / "model_golden.json").read_text(encoding="utf-8"))
    served = json.loads((DS / "reports" / "blind_final_eval.json").read_text(encoding="utf-8"))["models"]["best"]["sha256_16"]
    gsha = str(golden.get("model_sha256", golden.get("sha256", "")))[:16]
    gates.append(("S1 model files match golden fixture", bool(gsha) and gsha == served, f"golden {gsha} vs scored {served}"))
    worst = 0.0
    for name in ("test", "final"):
        rep = blind(name)
        if rep:
            v = rep["systems"]["model: best"]["false_alarm_rate"]["value"] or 0.0
            worst = max(worst, v)
    gates.append(("S2 false alarm on OTHER <= 0.30 (worst set)", worst <= 0.30, f"{worst:.3f}"))
    best_pos, best_prec, best_rec = 0, None, None
    for name in ("test", "final"):
        rep = blind(name)
        if rep:
            s = rep["systems"]["model: best"]
            if s["n_misconception"] > best_pos:
                best_pos = s["n_misconception"]
                best_prec = s["precision_when_flagged"]["value"]
                best_rec = s["misconception_recall"]["value"]
    gates.append(("P1 precision when flagged >= 0.80 on >= 30 positives",
                  best_pos >= 30 and (best_prec or 0) >= 0.80, f"{best_pos} positives, precision {best_prec}"))
    gates.append(("P2 recall >= 0.50 on that set", best_pos >= 30 and (best_rec or 0) >= 0.50, f"recall {best_rec}"))
    gates.append(("P3 labels made by independent people", False, "labels are model-assisted, treated as human by instruction"))
    gates.append(("P4 backend supplies compiler-warning counts", False, "model_runner passes none; 'on' forces abstain while features are missing"))
    for g, ok, note in gates:
        print(f"{'PASS' if ok else 'FAIL'}  {g}  [{note}]")
    shadow_ok = all(ok for g, ok, _ in gates if g.startswith("S"))
    on_ok = shadow_ok and all(ok for g, ok, _ in gates if g.startswith("P"))
    print(f"\nVERDICT: shadow {'CLEARED' if shadow_ok else 'BLOCKED'}; on {'CLEARED' if on_ok else 'BLOCKED'}")
    return 0 if shadow_ok else 1


if __name__ == "__main__":
    sys.exit(main())
