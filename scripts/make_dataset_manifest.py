"""Create a manifest that identifies a trained model and the data it came from.

    python scripts/make_dataset_manifest.py [--out data/misconception_dataset/models/dataset_manifest.json]
    python scripts/make_dataset_manifest.py --check

The manifest records:
- SHA-256 of labels.jsonl, features.csv and splits.csv;
- SHA-256 of the five model files, calibrator.json, label_encoder.json and metrics_v1.json;
- the git commit it was written at;
- the training profile and its parameters, the synthetic rule, and the row ids the trainer
  actually used (models/training_row_ids.txt, hashed and counted by origin).

Hashes read CRLF as LF, so a Windows checkout and a Linux checkout agree, and keys use forward
slashes. `--check` exits 1 if anything the manifest lists has changed, or if there is no manifest.

A model trained before the trainer wrote training_row_ids.txt has no row list; its manifest says so
in `training.row_ids_note` instead of pretending the data hashes identify the training rows.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 2

DATA_FILES = ("annotations/labels.jsonl", "features/features.csv", "splits/splits.csv")
MODEL_FILES = (
    "xgb_v1.json", "xgb_masked_v1.json", "xgb_common_v1.json", "xgb_best_v1.json",
    "xgb_execution_v1.json", "calibrator.json", "label_encoder.json", "metrics_v1.json",
)
ROW_IDS_FILE = "training_row_ids.txt"

CR, LF, CRLF = b"\r", b"\n", b"\r\n"


def sha256_file(path: Path) -> str:
    """SHA-256 of the file with CRLF read as LF.

    The tracked files are LF in git. A Windows checkout with core.autocrlf turns them into CRLF,
    which would change a plain hash; normalising makes this equal `git show <rev>:<path> | sha256sum`
    on every platform.
    """
    h = hashlib.sha256()
    held = b""
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            chunk = held + chunk
            held = CR if chunk.endswith(CR) else b""
            h.update((chunk[:-1] if held else chunk).replace(CRLF, LF))
    h.update(held)
    return h.hexdigest()


def row_ids_sha256(row_ids) -> str:
    """Hash of the sorted row ids, one per line: the same bytes the trainer writes to ROW_IDS_FILE."""
    return hashlib.sha256(("\n".join(sorted(row_ids)) + "\n").encode("utf-8")).hexdigest()


def write_training_row_ids(models_dir: Path, row_ids) -> Path:
    """Write the sorted ids of the rows a model was trained on, next to the model."""
    path = Path(models_dir) / ROW_IDS_FILE
    path.write_bytes(("\n".join(sorted(row_ids)) + "\n").encode("utf-8"))
    return path


def _key(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _git_commit(root: Path) -> str | None:
    try:
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() or None if done.returncode == 0 else None


PLAIN_FAMILY = ("plain", "plain_reg")  # profiles that select synthetic rows by prefix (trainer's PLAIN_FAMILY)


def _trainer_source() -> str:
    # Read constants from the trainer's source: importing the trainer needs numpy and xgboost,
    # which the CI job that runs --check does not install. Empty when there is no trainer.
    path = ROOT / "scripts" / "train_xgb_misconception.py"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _allowed_synthetic_prefixes(profile: dict) -> list[str] | None:
    """The synthetic families a plain-family model may train on; None for profiles that use them all."""
    if profile.get("synthetic_prefixes_allowed"):
        return profile["synthetic_prefixes_allowed"]
    if profile.get("name") not in PLAIN_FAMILY:
        return None
    for node in ast.parse(_trainer_source() or "").body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "PLAIN_SYNTHETIC_PREFIXES" for t in node.targets):
            return list(ast.literal_eval(node.value))
    return None


def _excluded_synthetic_prefixes(profile: dict) -> list[str] | None:
    """Families a plain-family model leaves out although their prefix is allowed (PLAIN_EXCLUDED_PREFIXES).

    Read from the metrics when the trainer recorded it, else from the default of TL_PLAIN_EXCLUDE in
    the trainer's source. A model trained with that variable set records it only in its metrics.
    """
    if profile.get("synthetic_prefixes_excluded") is not None:
        return profile["synthetic_prefixes_excluded"]
    if profile.get("name") not in PLAIN_FAMILY:
        return None
    m = re.search(r'TL_PLAIN_EXCLUDE"\s*,\s*"([^"]*)"', _trainer_source())
    return [x for x in m.group(1).split(",") if x] if m else None


def _training_block(ds: Path) -> dict:
    models = ds / "models"
    profile: dict = {}
    if (models / "metrics_v1.json").exists():
        profile = json.loads((models / "metrics_v1.json").read_text(encoding="utf-8")).get("profile") or {}
    name = profile.get("name")
    block: dict = {
        "profile": name,
        "params": profile.get("params"),
        "balance": profile.get("balance"),
        "synthetic_prefixes_allowed": _allowed_synthetic_prefixes(profile),
        "synthetic_prefixes_excluded": _excluded_synthetic_prefixes(profile),
        "synthetic_rule": (
            "SYNTHETIC rows are used only if row_id starts with an allowed prefix and not with an "
            "excluded one; every other SYNTHETIC row is excluded. Other rows are used only if "
            "label_source == 'human'."
            if name in PLAIN_FAMILY else
            "every SYNTHETIC row in the train split is used, weighted by the cross-validated multiplier."
            if name else None),
        "row_ids_file": None,
        "n_rows": None,
        "n_real_source": None,
        "n_synthetic": None,
        "row_ids_sha256": None,
        "row_ids_note": None,
    }
    ids_path = models / ROW_IDS_FILE
    if not ids_path.exists():
        block["row_ids_note"] = (
            "not recorded: this model was trained before the trainer wrote its row-id list, so the "
            "data hashes alone do not say which rows it used.")
        return block
    ids = [line for line in ids_path.read_text(encoding="utf-8").splitlines() if line]
    origin = {}
    with (ds / "annotations" / "labels.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
                origin[row["row_id"]] = row.get("dataset_source")
            except (ValueError, KeyError, TypeError):
                continue  # a damaged line must show up as a changed hash, not crash the check
    n_syn = sum(1 for r in ids if origin.get(r) == "SYNTHETIC")
    block.update(
        row_ids_file=_key(ids_path, ds.parents[1]),
        n_rows=len(ids), n_synthetic=n_syn, n_real_source=len(ids) - n_syn,
        row_ids_sha256=row_ids_sha256(ids),
    )
    return block


def build_manifest(root: Path | None = None) -> dict:
    root = Path(root) if root else ROOT
    ds = root / "data" / "misconception_dataset"

    def hashes(base: Path, names) -> dict:
        return {_key(base / n, root): (sha256_file(base / n) if (base / n).exists() else None) for n in names}

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git_commit(root),
        "files": hashes(ds, DATA_FILES),
        "model_files": hashes(ds / "models", MODEL_FILES + tuple(
            p.name for p in sorted((ds / "models").glob("xgb_execution_v1.bag*.json")))),
        "training": _training_block(ds),
    }


def differences(stored: dict, current: dict) -> list[str]:
    """What changed since `stored` was written.

    A manifest older than this schema, or one missing a section, is itself a change: it does not
    pin everything (an old manifest lists no model files), so it must not pass `--check`.
    """
    out = []
    if stored.get("schema_version", 1) < SCHEMA_VERSION:
        out.append(f"  manifest schema {stored.get('schema_version', 1)} is older than {SCHEMA_VERSION}: regenerate it")
    for section in ("files", "model_files"):
        if section not in stored:
            out.append(f"  section {section!r} missing from the manifest")
            continue
        for key, digest in current[section].items():
            if key in stored[section] and stored[section][key] != digest:
                out.append(f"  {key}: stored={stored[section][key]} current={digest}")
            elif key not in stored[section]:
                out.append(f"  {key}: stored=(missing) current={digest}")
    s_train, c_train = stored.get("training"), current["training"]
    if s_train is not None and s_train.get("row_ids_sha256") != c_train.get("row_ids_sha256"):
        out.append(f"  training row ids: stored={s_train.get('row_ids_sha256')} current={c_train.get('row_ids_sha256')}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "misconception_dataset" / "models" / "dataset_manifest.json"))
    ap.add_argument("--check", action="store_true",
                    help="only verify an existing manifest, don't write")
    args = ap.parse_args(argv)

    out_path = Path(args.out)
    manifest = build_manifest()

    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        changed = differences(existing, manifest)
        if not changed:
            print(f"[manifest] everything listed in {out_path} matches")
            return 0
        print(f"[manifest] WARNING — {len(changed)} item(s) changed since the manifest was written:")
        for line in changed:
            print(line)
        if args.check:
            return 1

    if args.check:
        print(f"[manifest] no manifest found at {out_path}")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"[manifest] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
