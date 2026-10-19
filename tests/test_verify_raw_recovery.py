"""G0 raw-recovery verifier tests (master plan §9.0 G0).

The verifier must:
- count CodeNet problem dirs, PROGpedia copies (9+8), CodeStream rows (46+5482)
  against injected expectations (defaults are the real G0 numbers);
- resolve 100% of *labeled-pool* paths (CODESTREAM + PROGPEDIA rows only —
  CodeNet is excluded from labels so a broken CodeNet path must not fail G0);
- SHA-256 spot-check a deterministic sample at >=98% match;
- write raw_recovery/recovery_manifest.json and exit 0/1.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from scripts.verify_raw_recovery import RecoveryExpectations, main, verify

CS_DIR = "CodeStream A Dataset of Iterative Programming Subm"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def _write_normalized(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    normalized = tmp_path / "normalized"
    fieldnames = [
        "submission_id",
        "dataset_source",
        "problem_id",
        "language",
        "source_code_path",
        "source_code_sha256",
    ]
    normalized.mkdir(parents=True, exist_ok=True)
    # Mirror the real normalized layout: submissions live in a subdirectory.
    (normalized / "submissions").mkdir(exist_ok=True)
    with (normalized / "submissions" / "submissions.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    return normalized


def _build_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """A tiny consistent raw root + normalized index. Returns (raw, normalized)."""
    raw = tmp_path / "raw"

    # CodeNet: 2 problem dirs
    for pid in ("p00001", "p00002"):
        (raw / "Project_CodeNet" / "Project_CodeNet" / "data" / pid / "C++").mkdir(
            parents=True
        )

    # PROGpedia: 1 + 1 problem dirs, one submission file each
    pg_code = b"int main() { return 0; }\n"
    pg_rel = "progpedia/00000006/ACCEPTED/00001_00001/main.c"
    pg_file = raw / pg_rel
    pg_file.parent.mkdir(parents=True)
    pg_file.write_bytes(pg_code)
    pg2_rel = "progpedia (1)/00000016/ACCEPTED/00001_00001/main.c"
    pg2_file = raw / pg2_rel
    pg2_file.parent.mkdir(parents=True)
    pg2_file.write_bytes(pg_code)

    # CodeStream: 1 problem row, 2 submission rows
    cs_code = "int main() { return 1; }"
    _write_csv(
        raw / CS_DIR / "Problem Data.csv",
        ["problem_id", "problem_description", "evaluation_test_cases"],
        [["prob1", "x" * 100, "[]"]],
    )
    _write_csv(
        raw / CS_DIR / "Submission Data.csv",
        [
            "submission_id",
            "user_id",
            "problem_id",
            "attempt_number",
            "programming_language",
            "source_code",
            "final_verdict",
            "verdict_sequence_trace",
        ],
        [
            ["sid1", "u1", "prob1", "1", "cpp", cs_code, "Wrong Answer", ""],
            ["sid2", "u1", "prob1", "2", "cpp", cs_code, "Accepted", ""],
        ],
    )

    cs_ref = f"{CS_DIR}/Submission Data.csv#sid1"
    cs_ref2 = f"{CS_DIR}/Submission Data.csv#sid2"
    rows = [
        {
            "submission_id": "tl-cs-sub-1",
            "dataset_source": "CODESTREAM",
            "problem_id": "prob1",
            "language": "cpp",
            "source_code_path": cs_ref,
            "source_code_sha256": _sha(cs_code.encode("utf-8")),
        },
        {
            "submission_id": "tl-cs-sub-2",
            "dataset_source": "CODESTREAM",
            "problem_id": "prob1",
            "language": "cpp",
            "source_code_path": cs_ref2,
            "source_code_sha256": _sha(cs_code.encode("utf-8")),
        },
        {
            "submission_id": "tl-pg-sub-1",
            "dataset_source": "PROGPEDIA",
            "problem_id": "00000006",
            "language": "c",
            "source_code_path": pg_rel,
            "source_code_sha256": _sha(pg_code),
        },
        {
            "submission_id": "tl-pg-sub-2",
            "dataset_source": "PROGPEDIA",
            "problem_id": "00000016",
            "language": "c",
            "source_code_path": pg2_rel,
            "source_code_sha256": _sha(pg_code),
        },
        # CodeNet is NOT in the labeled pool: its path does not exist on
        # purpose, and G0 must still pass.
        {
            "submission_id": "tl-cn-sub-1",
            "dataset_source": "PROJECT_CODENET",
            "problem_id": "p00001",
            "language": "cpp",
            "source_code_path": "Project_CodeNet/does/not/exist.cpp",
            "source_code_sha256": "0" * 64,
        },
    ]
    normalized = _write_normalized(tmp_path, rows)
    (normalized / "ingest_run_manifest.json").write_text(
        json.dumps(
            {
                "ingestion_run_id": "run-fixture",
                "flags": {"sources": ["codestream", "progpedia"], "inline_code": False},
            }
        ),
        encoding="utf-8",
    )
    return raw, normalized


def EXPECTATIONS() -> RecoveryExpectations:
    """G0 expectations sized for the fixture (defaults in the module are the
    real G0 numbers: 70 / (9,8) / 46 / 5482)."""
    return RecoveryExpectations(
        codenet_problem_dirs=2,
        progpedia_copies=(1, 1),
        codestream_problems=1,
        codestream_submissions=2,
        sha_sample_frac=1.0,
    )


def test_g0_passes_on_consistent_fixture(tmp_path):
    raw, normalized = _build_fixture(tmp_path)
    out = tmp_path / "recovery_manifest.json"

    manifest, ok = verify(raw, normalized, EXPECTATIONS(), out_path=out)

    assert ok, json.dumps(manifest, indent=2)
    assert out.exists(), "manifest must be written even as a build artifact"
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["kind"] == "raw_recovery"
    assert written["schema_version"] == "1.0"
    # every count check present and passing
    for name in (
        "codenet_problem_dirs",
        "progpedia_copy_1_dirs",
        "progpedia_copy_2_dirs",
        "codestream_problem_rows",
        "codestream_submission_rows",
    ):
        assert written["checks"][name]["pass"] is True, name
    assert written["path_resolution"]["labeled_pool_rows"] == 4
    assert written["path_resolution"]["resolved"] == 4
    assert written["path_resolution"]["pass"] is True
    assert written["sha256_sample"]["rate"] == 1.0
    assert written["sha256_sample"]["pass"] is True
    # ingest flags carried through
    assert written["ingest_flags"] is not None
    # pending items owned by other lanes are explicit nulls, not invented values
    assert written["g0b_docker_digest"] is None
    assert written["g0c_seed_audit"] is None


def test_missing_codenet_dir_fails(tmp_path):
    raw, normalized = _build_fixture(tmp_path)
    import shutil

    shutil.rmtree(raw / "Project_CodeNet" / "Project_CodeNet" / "data" / "p00002")

    manifest, ok = verify(raw, normalized, EXPECTATIONS(), out_path=tmp_path / "m.json")

    assert not ok
    assert manifest["checks"]["codenet_problem_dirs"]["pass"] is False
    assert manifest["checks"]["codenet_problem_dirs"]["observed"] == 1


def test_wrong_codestream_counts_fail(tmp_path):
    raw, normalized = _build_fixture(tmp_path)
    expectations = RecoveryExpectations(
        codenet_problem_dirs=2,
        progpedia_copies=(1, 1),
        codestream_problems=46,  # fixture only has 1
        codestream_submissions=2,
        sha_sample_frac=1.0,
    )

    manifest, ok = verify(raw, normalized, expectations, out_path=tmp_path / "m.json")

    assert not ok
    assert manifest["checks"]["codestream_problem_rows"]["pass"] is False


def test_unresolved_labeled_pool_path_fails_and_names_the_row(tmp_path):
    raw, normalized = _build_fixture(tmp_path)
    # point one CodeStream row at a submission_id absent from the raw CSV
    sub_csv = normalized / "submissions" / "submissions.csv"
    text = sub_csv.read_text(encoding="utf-8")
    sub_csv.write_text(
        text.replace("#sid2", "#sid-missing"), encoding="utf-8"
    )

    manifest, ok = verify(raw, normalized, EXPECTATIONS(), out_path=tmp_path / "m.json")

    assert not ok
    pr = manifest["path_resolution"]
    assert pr["pass"] is False
    assert pr["resolved"] == 3
    assert pr["failures"][0]["submission_id"] == "tl-cs-sub-2"
    assert "sid-missing" in pr["failures"][0]["source_code_path"]


def test_codenet_is_not_part_of_the_labeled_pool(tmp_path):
    """The fixture ships a deliberately broken CodeNet path; G0 must pass."""
    raw, normalized = _build_fixture(tmp_path)

    manifest, ok = verify(raw, normalized, EXPECTATIONS(), out_path=tmp_path / "m.json")

    assert ok, json.dumps(manifest, indent=2)
    assert manifest["path_resolution"]["labeled_pool_rows"] == 4


def test_sha256_sample_detects_tampering(tmp_path):
    raw, normalized = _build_fixture(tmp_path)
    # tamper the PROGpedia file after the index was built
    pg_file = raw / "progpedia" / "00000006" / "ACCEPTED" / "00001_00001" / "main.c"
    pg_file.write_bytes(b"int main() { return 1; }  // tampered\n")

    manifest, ok = verify(raw, normalized, EXPECTATIONS(), out_path=tmp_path / "m.json")

    assert not ok
    sample = manifest["sha256_sample"]
    assert sample["pass"] is False
    assert sample["matched"] == 3
    assert sample["sampled"] == 4
    assert sample["mismatches"][0]["submission_id"] == "tl-pg-sub-1"


def test_sample_is_deterministic_for_a_seed(tmp_path):
    raw, normalized = _build_fixture(tmp_path)
    expectations = RecoveryExpectations(
        codenet_problem_dirs=2,
        progpedia_copies=(1, 1),
        codestream_problems=1,
        codestream_submissions=2,
        sha_sample_frac=0.5,
    )

    m1, _ = verify(raw, normalized, expectations, out_path=tmp_path / "a.json", seed=7)
    m2, _ = verify(raw, normalized, expectations, out_path=tmp_path / "b.json", seed=7)
    m3, _ = verify(raw, normalized, expectations, out_path=tmp_path / "c.json", seed=8)

    assert m1["sha256_sample"]["sampled_ids"] == m2["sha256_sample"]["sampled_ids"]
    assert m1["sha256_sample"]["seed"] == 7
    assert m3["sha256_sample"]["seed"] == 8


def test_main_writes_manifest_and_returns_zero(tmp_path, capsys):
    raw, normalized = _build_fixture(tmp_path)
    out = tmp_path / "recovery_manifest.json"

    rc = main(
        [
            "--raw-root",
            str(raw),
            "--normalized",
            str(normalized),
            "--out",
            str(out),
            "--codenet-dirs",
            "2",
            "--progpedia-copies",
            "1",
            "1",
            "--codestream-problems",
            "1",
            "--codestream-submissions",
            "2",
            "--sample-frac",
            "1.0",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0, captured.out + captured.err
    assert "PASS" in captured.out
    assert json.loads(out.read_text(encoding="utf-8"))["kind"] == "raw_recovery"


def test_main_returns_one_on_failure(tmp_path, capsys):
    raw, normalized = _build_fixture(tmp_path)

    rc = main(
        [
            "--raw-root",
            str(raw),
            "--normalized",
            str(normalized),
            "--out",
            str(tmp_path / "m.json"),
            "--codenet-dirs",
            "70",  # fixture only has 2
            "--progpedia-copies",
            "9",
            "8",
            "--codestream-problems",
            "46",
            "--codestream-submissions",
            "5482",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "FAIL" in captured.out


def test_defaults_match_the_g0_gate_numbers():
    defaults = RecoveryExpectations()
    assert defaults.codenet_problem_dirs == 70
    assert defaults.progpedia_copies == (9, 8)
    assert defaults.codestream_problems == 46
    assert defaults.codestream_submissions == 5482
    assert defaults.sha_sample_frac == 0.05
    assert defaults.sha_min_rate == 0.98
