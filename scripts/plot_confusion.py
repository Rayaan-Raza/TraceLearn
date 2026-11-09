"""Confusion matrices (PNG) of the served `best` model on the blind sets. Read-only: scores nothing new
beyond what eval_blind_test.py already scored; writes reports/confusion_<set>.png and prints accuracy.

    wsl python3 scripts/plot_confusion.py score   # writes reports/blind_predictions.json (needs raw data)
    python scripts/plot_confusion.py plot         # draws the PNGs (needs matplotlib)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DS = ROOT / "data" / "misconception_dataset"


def items_for(name):
    from codestream_common import find_raw, load_problems, load_submissions
    from eval_real_data import feature_row, flatten_blocks
    from tracelearn_features.schema import feature_names
    labels = json.loads((DS / "review" / "blind_labels" / f"{name}.json").read_text(encoding="utf-8"))
    manifest = json.loads((DS / "cache" / "label_batches" / name / "manifest.json").read_text(encoding="utf-8"))
    ex = {}
    for line in (DS / "cache" / f"label_exec_{name}.jsonl").open(encoding="utf-8"):
        r = json.loads(line); ex[r["submission_id"]] = r["result"]
    raw = find_raw("/mnt/g/TraceLearn/Datasets_RAW")
    probs = load_problems(raw); subs = {s.submission_id: s for s in load_submissions(raw)}
    out = []
    for m in manifest:
        lab = labels.get(m["item_id"])
        if lab is None or lab["label"] == "UNCERTAIN" or m["submission_id"] not in ex:
            continue
        s = subs[m["submission_id"]]
        out.append((lab["label"], flatten_blocks(feature_row(s, probs[s.problem_id], ex[m["submission_id"]]), feature_names())))
    return out


def short(c):
    return c.replace("CPP_", "").replace("_", " ").title() if c != "ABSTAIN" else "Abstain"


def score():
    from backend.app.diagnosis.xgb_classifier import ModelClassifier
    model = ModelClassifier.load("best")
    out = {}
    for name in ("final", "test"):
        res = []
        for t, f in items_for(name):
            p = model.predict(f)
            res.append([t, "ABSTAIN" if p.abstained else p.top_label])
        out[name] = res
    (DS / "reports" / "blind_predictions.json").write_text(json.dumps(out), encoding="utf-8")


def plot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    data = json.loads((DS / "reports" / "blind_predictions.json").read_text(encoding="utf-8"))
    for name, title in (("final", "Final set (untouched)"), ("test", "Development set")):
        truth = [t for t, _ in data[name]]; pred = [p for _, p in data[name]]
        rows = sorted(set(truth))
        cols = sorted((set(truth) | set(pred)) - {"ABSTAIN"}) + (["ABSTAIN"] if "ABSTAIN" in pred else [])
        M = np.array([[sum(1 for t, p in zip(truth, pred) if t == r and p == c) for c in cols] for r in rows])
        acc = sum(t == p for t, p in zip(truth, pred)) / len(truth)
        fig, ax = plt.subplots(figsize=(1.2 * len(cols) + 3, 0.8 * len(rows) + 3.5))
        ax.imshow(M, cmap="Blues")
        ax.set_xticks(range(len(cols)), [short(c) for c in cols], rotation=40, ha="right")
        ax.set_yticks(range(len(rows)), [short(r) for r in rows])
        for i in range(len(rows)):
            for j in range(len(cols)):
                ax.text(j, i, M[i, j], ha="center", va="center", color="white" if M[i, j] > M.max() / 2 else "black")
        ax.set_xlabel("Predicted"); ax.set_ylabel("Labelled (assumed-human)")
        ax.set_title(f"{title}: accuracy {acc:.3f} (n={len(truth)})")
        fig.tight_layout(); out = DS / "reports" / f"confusion_{name}.png"; fig.savefig(out, dpi=150); plt.close(fig)
        mis = [(t, p) for t, p in zip(truth, pred) if t != "CPP_OTHER_ERROR"]
        print(name, "accuracy", round(acc, 3), "| always-OTHER", round(Counter(truth)["CPP_OTHER_ERROR"] / len(truth), 3),
              "| misconception recall", sum(t == p for t, p in mis), "/", len(mis), "| wrote", out.name)


def plot_heldout():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    d = json.loads((DS / "reports" / "heldout_predictions.json").read_text(encoding="utf-8"))
    col = d["columns"].index("model: best")
    for scope in ("all", "PROGPEDIA"):
        rows = [r for r in d["rows"] if scope == "all" or r[1] == scope]
        truth = [r[2] for r in rows]; pred = [r[col] for r in rows]
        rl = sorted(set(truth))
        cl = sorted((set(truth) | set(pred)) - {"ABSTAIN"}) + (["ABSTAIN"] if "ABSTAIN" in pred else [])
        M = np.array([[sum(1 for t, p in zip(truth, pred) if t == a and p == b) for b in cl] for a in rl])
        fig, ax = plt.subplots(figsize=(1.2 * len(cl) + 3, 0.8 * len(rl) + 3.5))
        ax.imshow(M, cmap="Blues")
        ax.set_xticks(range(len(cl)), [short(c) for c in cl], rotation=40, ha="right")
        ax.set_yticks(range(len(rl)), [short(c) for c in rl])
        for i in range(len(rl)):
            for j in range(len(cl)):
                ax.text(j, i, M[i, j], ha="center", va="center", color="white" if M[i, j] > M.max() / 2 else "black")
        ax.set_xlabel("Predicted"); ax.set_ylabel("Labelled (annotator consensus)")
        ax.set_title(f"Held-out problems, {scope}: n={len(rows)}, accuracy {sum(a == b for a, b in zip(truth, pred)) / len(rows):.3f}")
        fig.tight_layout(); fig.savefig(DS / "reports" / f"confusion_heldout_{scope.lower()}.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    {"score": score, "plot": plot, "heldout": plot_heldout}[sys.argv[1]]()
