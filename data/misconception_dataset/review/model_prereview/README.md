# Model pre-review sheets — how to sign off

These sheets hold a **model's** (Claude's) review of weak labels and its proposed
labels for dev-gold items. **Nothing in a sheet is a label until a person signs it.**
The model never relabels a row on its own authority.

| Sheet | What it is |
|---|---|
| `weak_labels_codestream.csv` | 33 CodeStream weak / repair-verified labels, each checked against the code and the sandbox evidence |
| `weak_labels_progpedia.csv` | the 150 PROGPedia `pg-3` (array-bounds rule) labels, checked against the code, the problem limits and, where available, the execution of the submission on the oracle tests |
| `dev_gold_*.csv` / `iid_test_*.csv` | new items with no prior label (`model_verdict = label`), proposed for the dev-gold calibration pool or the IID test |

## What a person fills in

Fill only these columns (leave the model's columns alone):

| Column | Value |
|---|---|
| `human_verdict` | `agree` (the model's `model_label` is right), `disagree` (it is wrong) or `unsure` |
| `human_label` | required on `disagree`: one `tl-cpp-v2` class, or `UNCERTAIN` |
| `signed_off_by` | your name |
| `signed_off_at` | date (YYYY-MM-DD) |
| `human_notes` | optional |

**Start with the rows where `spotcheck = 1`** (a seeded 20% sample). Judge each one
from the code (`source_record_id` / `submission_id`) yourself before reading
`model_rationale`, so you are not anchored by it.

## What happens after you sign

Run `python scripts/apply_prereview_signoff.py --raw-root <Datasets_RAW>` (or
`--dry-run` to preview), then re-merge and retrain.

* A row you signed is decided by **you**: `agree` keeps the model label;
  `disagree` uses your `human_label`.
* The **unsigned** rest of a sheet is accepted on the model's word only when
  **every** spot-check row is signed **and** you agreed on **≥ 90%** of the signed
  rows (`unsure` counts neither way). Even then:
  * a model `uncertain` row is never accepted,
  * a model-only verdict can **confirm** a weak label or **reject** (drop) it,
    but never **relabel** it — a relabel needs your signature.
* Otherwise unsigned rows change nothing.

Effects: `annotations/label_review_decisions.jsonl` (confirm / relabel / reject,
applied by `merge_dataset.py`), the per-LF audit counts in
`annotations/lf_audits.csv` (these set the Beta-bound weak-label confidence), and
new human rows in `annotations/tier1d_human_review.jsonl` for dev-gold / IID
items. `signoff_report.md` records what was decided and why.
