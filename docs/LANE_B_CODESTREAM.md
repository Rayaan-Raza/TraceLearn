# Lane B — CodeStream labeling and the shared sandbox (owner: Umaima)

Runbook for Master Plan v4.1 §5 (Lane B), §9.2 (U0–U5) and gate G6.

## Pipeline

| Step | Command | Output | Gate |
|---|---|---|---|
| U0 harness | `python -m pytest tests/misconception_dataset` · `python scripts/sandbox_manifest.py --image tracelearn-sandbox:0.2.0` | `sandbox_runner/`, `raw_recovery/recovery_manifest.json` | G0b |
| Clusters | `python scripts/cluster_codestream_problems.py` | `splits/codestream_clusters.csv`, `reports/codestream_cluster_split.md` | before E1 mining |
| U1 execute | `python scripts/execute_codestream.py --workers N` | `cache/codestream_exec.jsonl` (gitignored), `reports/u1_executor_report.md` | U1 |
| U3 pilot | `python scripts/label_weak_codestream.py --pilot 150` | `annotations/*_pilot.*`, `reports/u2_labeling_report_pilot.md` | G3 input |
| U2/U4 label | `python scripts/label_weak_codestream.py [--explore]` | `annotations/tier1a_codestream.jsonl`, `annotations/review/*`, reports | G5 |
| Audit | fill `annotations/review/lf_audit_sheet.csv` → totals into `annotations/lf_audits.csv`, re-run the labeler | Beta-bound `label_confidence` | G5 |
| U5 forms | `python scripts/build_annotation_forms.py` | `annotations/forms/*`, hidden `annotations/forms_key/` | G6 |
| H1 adjudicate | `python scripts/adjudicate_gold.py` | `annotations/gold.jsonl`, `dev_gold.jsonl`, `reports/gold_agreement_report.md` | G6 |

Raw data location: `--raw <Datasets_RAW>` or `TRACELEARN_RAW`. The default search
includes `G:\TraceLearn\Datasets_RAW` and `~/Downloads/TraceLearn/TraceLearn/Datasets_RAW`.

## Label sources in `tier1a_codestream.jsonl`

- `repair_verified`: an LF fired, and one inverse-operator edit of that class makes
  every test pass. The edit and its test proof are stored in `repair`. These count
  toward the **certain** floor (Layer 4).
- `weak_rule`: exactly one floor-class LF fired and no repair verified. This is
  **silver**: it sits on top of the floor and is never load-bearing.

Every row carries `split_pool`. Rows from `dev_gold` and `test` clusters **must not
enter training** (§13.4). They are the gold-form pool.

## Review pools (never auto-labeled)

| File | What | Next step |
|---|---|---|
| `review/multi_signal.jsonl` | LFs for different classes fired, or several repairs verified | human promotion or `UNCERTAIN` |
| `review/discovery_candidates.jsonl` | classes 4, 8, 9, 10 (detector fires, ranked: verified repair first) | 2 h/person/class review (§13.5); found-per-reviewed = prevalence estimate |
| `review/repair_discovered.jsonl` | `--explore` only: no LF fired, but a single inverse operator fixes every test | H2 human confirmation |
| `review/other_error_candidates.jsonl` | seeded sample of rows where no LF fired | human confirmation → the only source of real `OTHER_ERROR` |

Rows where no LF fired are **never** labeled `OTHER_ERROR` automatically (§13.5 fix).

## Confidence

`label_confidence = min(0.85, q20(Beta(1 + correct, 1 + audited − correct)))`. The keys
are LF names (for `weak_rule`) and `repair_verified:<CLASS>`. Until audits are entered
the value is 0.2 (the Beta(1,1) bound with no data). This is deliberate.

## Isolation status

The bulk run used the **local** backend: rlimits, uid 65534, an empty network
namespace via `unshare -n` + `setpriv`, process-group kill, and capped output. The
**docker** backend (`--network none`, read-only root, tmpfs, `--pids-limit 64`,
`--cap-drop ALL`) is implemented and unit-tested for its flags. The image still has
to be built and pinned by digest on a host that can pull `ubuntu:24.04`. That is
the open G0b item.
