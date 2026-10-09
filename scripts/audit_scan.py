"""Non-destructive scanner for TraceLearn raw datasets.

Reads file trees. Writes counts and samples to the console.
Does not modify any raw file.
"""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from pathlib import Path

RAW = Path(r"G:\TraceLearn\Datasets_RAW")


def human(n: int) -> str:
    return f"{n / (1024 * 1024):.2f} MB"


def scan_tree(root: Path) -> tuple[int, int, Counter]:
    total_files = 0
    total_bytes = 0
    exts: Counter = Counter()
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            p = Path(dirpath) / name
            try:
                size = p.stat().st_size
            except OSError:
                continue
            total_files += 1
            total_bytes += size
            exts[p.suffix.lower() or "<none>"] += 1
    return total_files, total_bytes, exts


def report(name: str, root: Path) -> None:
    if not root.exists():
        print(f"[MISSING] {name}: {root}")
        return
    files, size, exts = scan_tree(root)
    print(f"[DIR] {name}")
    print(f"    path   : {root}")
    print(f"    files  : {files}")
    print(f"    size   : {human(size)}")
    print(f"    top ext: {exts.most_common(8)}")
    print()


def read_text(path: Path, limit: int = 400) -> str:
    raw = path.read_bytes()[:limit * 4]
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)[:limit]
        except UnicodeDecodeError:
            continue
    return "<undecodable>"


def csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        return next(reader, [])


def main() -> None:
    report("Project_CodeNet", RAW / "Project_CodeNet")
    report("CodeStream", RAW / "CodeStream A Dataset of Iterative Programming Subm")
    report("progpedia", RAW / "progpedia")
    report("progpedia (1)", RAW / "progpedia (1)")
    report("TraceLearn_Dataset_Starter", RAW / "TraceLearn_Dataset_Starter")
    report("poc_data", RAW / "poc_data")

    print("=== CodeStream columns ===")
    cs = RAW / "CodeStream A Dataset of Iterative Programming Subm"
    print("problems:", csv_header(cs / "Problem Data.csv"))
    print("submissions:", csv_header(cs / "Submission Data.csv"))

    print()
    print("=== CodeStream problem row sample ===")
    with (cs / "Problem Data.csv").open("r", encoding="utf-8", errors="replace", newline="") as fh:
        row = next(csv.DictReader(fh), {})
    for key, value in row.items():
        print(f"  {key}: {str(value)[:300]!r}")

    print()
    print("=== CodeStream language distribution (top) ===")
    langs: Counter = Counter()
    verdicts: Counter = Counter()
    with (cs / "Submission Data.csv").open("r", encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            langs[row.get("programming_language", "")] += 1
            verdicts[row.get("final_verdict", "")] += 1
    print("languages:", langs.most_common())
    print("verdicts:", verdicts.most_common())

    print()
    print("=== PROGpedia problem folder scan ===")
    for label, root in (("progpedia", RAW / "progpedia"), ("progpedia (1)", RAW / "progpedia (1)")):
        problems = sorted(p for p in root.iterdir() if p.is_dir())
        lang_exts: Counter = Counter()
        verdicts2: Counter = Counter()
        stmt = 0
        for prob in problems:
            if (prob / "statement.md").exists():
                stmt += 1
            for sub in prob.iterdir():
                if sub.is_dir():
                    verdicts2[sub.name] += 1
                    for f in sub.rglob("*"):
                        if f.is_file():
                            lang_exts[f.suffix.lower()] += 1
        print(f"{label}: problems={len(problems)} statements={stmt}")
        print(f"    verdict dirs: {verdicts2.most_common()}")
        print(f"    file ext    : {lang_exts.most_common(8)}")

    print()
    print("=== Project_CodeNet structure ===")
    cn = RAW / "Project_CodeNet" / "Project_CodeNet"
    print("metadata dir present:", (cn / "metadata").exists())
    print("derived dir present :", (cn / "derived").exists())
    data = cn / "data"
    problems = sorted(p for p in data.iterdir() if p.is_dir())
    cpp_files = 0
    all_files = 0
    langs3: Counter = Counter()
    for prob in problems:
        for lang_dir in prob.iterdir():
            if lang_dir.is_dir():
                langs3[lang_dir.name] += 1
                for f in lang_dir.iterdir():
                    if f.is_file():
                        all_files += 1
                        if f.suffix.lower() in {".cpp", ".cc", ".cxx"}:
                            cpp_files += 1
    print(f"problem folders in data/: {len(problems)}")
    print(f"source files            : {all_files}")
    print(f"C++ source files        : {cpp_files}")
    print(f"language dirs (problems): {langs3.most_common()}")

    print()
    print("=== poc_data problems.json sample ===")
    pj = RAW / "poc_data" / "data" / "problems" / "problems.json"
    obj = json.loads(pj.read_text(encoding="utf-8"))
    print("type:", type(obj).__name__, "len:", len(obj))
    sample = obj[0] if isinstance(obj, list) else obj
    print(json.dumps(sample, indent=2)[:600])


if __name__ == "__main__":
    main()
