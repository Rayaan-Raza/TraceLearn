"""Tests for scripts/make_dataset_manifest.py."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from make_dataset_manifest import build_manifest, sha256_file


class TestSha256File:
    def test_known_content(self, tmp_path):
        import hashlib
        content = b"hello dataset"
        p = tmp_path / "file.txt"
        p.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert sha256_file(p) == expected

    def test_different_content_different_hash(self, tmp_path):
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_bytes(b"aaaa")
        b.write_bytes(b"bbbb")
        assert sha256_file(a) != sha256_file(b)


class TestBuildManifest:
    def test_manifest_has_created_at(self):
        m = build_manifest()
        assert "created_at" in m
        assert "T" in m["created_at"]  # ISO 8601

    def test_manifest_has_files_key(self):
        m = build_manifest()
        assert "files" in m
        assert isinstance(m["files"], dict)

    def test_manifest_includes_expected_files(self):
        m = build_manifest()
        keys = set(m["files"].keys())
        for suffix in ("labels.jsonl", "features.csv", "splits.csv"):
            assert any(suffix in k for k in keys), f"{suffix} not in manifest files"

    def test_manifest_hashes_are_64_char_hex(self):
        m = build_manifest()
        for path, digest in m["files"].items():
            assert len(digest) == 64, f"{path} hash has wrong length"
            assert all(c in "0123456789abcdef" for c in digest), f"{path} hash not hex"


class TestCrossPlatform:
    """--check must agree on Windows and Linux (audit finding on claim E13)."""

    def test_keys_use_forward_slashes(self):
        for key in build_manifest()["files"]:
            assert "\\" not in key, key

    def test_check_passes_against_a_manifest_written_on_linux(self, tmp_path):
        import subprocess

        stored = tmp_path / "dataset_manifest.json"
        m = build_manifest()
        m["files"] = {k.replace("\\", "/"): v for k, v in m["files"].items()}
        stored.write_text(json.dumps(m), encoding="utf-8")
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "make_dataset_manifest.py"),
             "--out", str(stored), "--check"],
            capture_output=True, text=True,
        )
        assert done.returncode == 0, done.stdout + done.stderr

    def test_hash_ignores_checkout_line_endings(self, tmp_path):
        lf = tmp_path / "lf.csv"
        crlf = tmp_path / "crlf.csv"
        lf.write_bytes(b"a,b\n1,2\n")
        crlf.write_bytes(b"a,b\r\n1,2\r\n")
        assert sha256_file(lf) == sha256_file(crlf)

    def test_hash_handles_crlf_split_across_chunks(self, tmp_path):
        import hashlib

        body = b"x" * ((1 << 20) - 1) + b"\r\n" + b"tail\n"
        p = tmp_path / "big.txt"
        p.write_bytes(body)
        assert sha256_file(p) == hashlib.sha256(body.replace(b"\r\n", b"\n")).hexdigest()


# ----------------------------------------------------------------- identifying a model, not only a dataset

import make_dataset_manifest as mdm  # noqa: E402


def _tree(tmp_path, *, with_row_ids=True):
    """A small repo-shaped tree: three data files, eight model files, optionally the trainer's row ids."""
    ds = tmp_path / "data" / "misconception_dataset"
    for rel, body in {
        "annotations/labels.jsonl": (
            '{"row_id": "r1", "dataset_source": "PROGPEDIA"}\n'
            '{"row_id": "r2", "dataset_source": "SYNTHETIC"}\n'
            '{"row_id": "r3", "dataset_source": "PROGPEDIA"}\n'),
        "features/features.csv": "row_id,label\nr1,a\nr2,b\nr3,c\n",
        "splits/splits.csv": "row_id,cluster_id,split\nr1,c1,train\nr2,c2,train\nr3,c3,test\n",
    }.items():
        (ds / rel).parent.mkdir(parents=True, exist_ok=True)
        (ds / rel).write_text(body, encoding="utf-8", newline="\n")
    models = ds / "models"
    models.mkdir(parents=True, exist_ok=True)
    for name in mdm.MODEL_FILES:
        (models / name).write_text(f'{{"file": "{name}"}}\n', encoding="utf-8", newline="\n")
    profile = {"name": "plain", "params": {"max_depth": 3}, "balance": "none", "synthetic_prefixes_allowed": ["stu-"]}
    (models / "metrics_v1.json").write_text(json.dumps({"profile": profile}), encoding="utf-8", newline="\n")
    if with_row_ids:
        mdm.write_training_row_ids(models, ["r2", "r1"])
    return ds


def _write_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(mdm, "ROOT", tmp_path)
    out = tmp_path / "manifest.json"
    out.write_text(json.dumps(mdm.build_manifest()), encoding="utf-8")
    return out


class TestModelManifest:
    def test_lists_all_eight_model_files(self, tmp_path):
        _tree(tmp_path)
        m = mdm.build_manifest(tmp_path)
        assert sorted(Path(k).name for k in m["model_files"]) == sorted(mdm.MODEL_FILES)
        assert all(len(v) == 64 for v in m["model_files"].values())

    def test_training_block_counts_the_rows_actually_trained_on(self, tmp_path):
        ds = _tree(tmp_path)
        t = mdm.build_manifest(tmp_path)["training"]
        assert (t["n_rows"], t["n_real_source"], t["n_synthetic"]) == (2, 1, 1)
        assert t["profile"] == "plain" and t["synthetic_prefixes_allowed"] == ["stu-"]
        assert t["row_ids_sha256"] == mdm.row_ids_sha256(["r1", "r2"])
        assert t["row_ids_sha256"] == mdm.sha256_file(ds / "models" / mdm.ROW_IDS_FILE)

    def test_a_model_without_a_row_list_says_so(self, tmp_path):
        _tree(tmp_path, with_row_ids=False)
        t = mdm.build_manifest(tmp_path)["training"]
        assert t["row_ids_sha256"] is None and t["n_rows"] is None
        assert "not recorded" in t["row_ids_note"]

    def test_records_the_git_commit_when_there_is_one(self):
        commit = build_manifest()["git_commit"]
        assert commit is None or (len(commit) == 40 and set(commit) <= set("0123456789abcdef"))


class TestCheck:
    def test_matching_manifest_exits_zero(self, tmp_path, monkeypatch):
        _tree(tmp_path)
        out = _write_manifest(tmp_path, monkeypatch)
        assert mdm.main(["--out", str(out), "--check"]) == 0

    @pytest.mark.parametrize("rel", [
        "annotations/labels.jsonl", "features/features.csv", "splits/splits.csv",
        "models/xgb_execution_v1.json", "models/calibrator.json", "models/training_row_ids.txt",
    ])
    def test_editing_one_file_exits_one(self, tmp_path, monkeypatch, rel):
        ds = _tree(tmp_path)
        out = _write_manifest(tmp_path, monkeypatch)
        with (ds / rel).open("a", encoding="utf-8", newline="\n") as fh:
            fh.write("x\n")
        assert mdm.main(["--out", str(out), "--check"]) == 1

    def test_no_manifest_exits_one(self, tmp_path, monkeypatch):
        _tree(tmp_path)
        monkeypatch.setattr(mdm, "ROOT", tmp_path)
        assert mdm.main(["--out", str(tmp_path / "none.json"), "--check"]) == 1

    def test_an_older_manifest_with_only_data_hashes_still_checks(self, tmp_path, monkeypatch):
        _tree(tmp_path)
        monkeypatch.setattr(mdm, "ROOT", tmp_path)
        full = mdm.build_manifest()
        out = tmp_path / "v1.json"
        out.write_text(json.dumps({"created_at": "x", "files": full["files"]}), encoding="utf-8")
        assert mdm.main(["--out", str(out), "--check"]) == 0
