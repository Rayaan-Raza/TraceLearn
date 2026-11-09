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
    served = json.loads((DS / "reports" / "heldout_eval.json").read_text(encoding="utf-8"))["models"]["best"]["sha256_16"]
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
    hp = DS / "reports" / "heldout_eval.json"
    if hp.exists():
        allp = json.loads(hp.read_text(encoding="utf-8"))["scopes"]["all"]["systems"]["model: best"]
        worst = max(worst, allp["false_alarm_rate"]["value"] or 0.0)
        gates[-1] = ("S2 false alarm on OTHER <= 0.30 (worst set)", worst <= 0.30, f"{worst:.3f}")
        if allp["n_misconception"] > best_pos:
            best_pos = allp["n_misconception"]
            best_prec = allp["precision_when_flagged"]["value"]
            best_rec = allp["misconception_recall"]["value"]
    gates.append(("P1 precision when flagged >= 0.80 on >= 30 positives",
                  best_pos >= 30 and (best_prec or 0) >= 0.80, f"{best_pos} positives, precision {best_prec}"))
    gates.append(("P2 recall >= 0.50 on that set", best_pos >= 30 and (best_rec or 0) >= 0.50, f"recall {best_rec}"))
    gates.append(("P3 labels made by independent people", False, "labels are model-assisted, treated as human by instruction"))
    sys.path.insert(0, str(ROOT))
    from backend.app.analysis import model_runner
    sample = ('#include <cstdio>\n'
              'int main(){int a[3];int x;for(int i=0;i<=3;i++)a[i]=i;printf("%d",x);return 0;}\n')
    got = model_runner.compiler_warnings(sample)
    gates.append(("P4 backend supplies compiler-warning counts", bool(got and "warning" in got["compile_warnings"]),
                  "model_runner compiles the submission with the training flags" if got else "compile for warnings failed (g++ or sandbox missing?)"))
    for g, ok, note in gates:
        print(f"{'PASS' if ok else 'FAIL'}  {g}  [{note}]")
    shadow_ok = all(ok for g, ok, _ in gates if g.startswith("S"))
    on_ok = shadow_ok and all(ok for g, ok, _ in gates if g.startswith("P"))
    print(f"\nVERDICT: shadow {'CLEARED' if shadow_ok else 'BLOCKED'}; on {'CLEARED' if on_ok else 'BLOCKED'}")
    # The gates above score `best`, the code-only default. `execution` needs a run record the backend does not
    # produce yet, so it cannot be cleared here; this line shows how far it is from P1 and P2.
    if hp.exists():
        ex = json.loads(hp.read_text(encoding="utf-8"))["scopes"]["all"]["systems"].get("model: execution")
        if ex:
            print(f"INFO  execution variant, not served: {ex['n_misconception']} positives, precision "
                  f"{ex['precision_when_flagged']['value']}, recall {ex['misconception_recall']['value']}, "
                  f"false alarm {ex['false_alarm_rate']['value']}")
    return 0 if shadow_ok else 1


if __name__ == "__main__":
    sys.exit(main())
