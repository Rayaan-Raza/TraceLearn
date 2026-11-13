"""Create a dataset manifest that pins the files used to train a model.

    python scripts/make_dataset_manifest.py [--out data/misconception_dataset/models/dataset_manifest.json]

Records SHA-256 hashes of:
- annotations/labels.jsonl
- features/features.csv
- splits/splits.csv

The manifest is written alongside the model files so that any future
training run can verify it is working from the same data snapshot. If the
manifest already exists and the hashes match, the script exits cleanly. If
the hashes differ (data has changed since the last training run), the script
prints a warning so the caller knows the model and dataset are out of sync.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "misconception_dataset"

MANIFEST_FILES = [
    DS / "annotations" / "labels.jsonl",
    DS / "features" / "features.csv",
    DS / "splits" / "splits.csv",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest() -> dict:
    return {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "files": {str(p.relative_to(ROOT)): sha256_file(p) for p in MANIFEST_FILES},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DS / "models" / "dataset_manifest.json"))
    ap.add_argument("--check", action="store_true",
                    help="only verify an existing manifest, don't write")
    args = ap.parse_args()

    out_path = Path(args.out)
    manifest = build_manifest()

    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        mismatches = [
            f"  {k}: stored={existing['files'].get(k, '(missing)')} current={v}"
            for k, v in manifest["files"].items()
            if existing["files"].get(k) != v
        ]
        if not mismatches:
            print(f"[manifest] all {len(manifest['files'])} files match {out_path}")
            return 0
        print(f"[manifest] WARNING — {len(mismatches)} file(s) changed since manifest was written:")
        for m in mismatches:
            print(m)
        if args.check:
            return 1

    if args.check:
        print(f"[manifest] no manifest found at {out_path}")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"[manifest] wrote {out_path} ({len(manifest['files'])} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
