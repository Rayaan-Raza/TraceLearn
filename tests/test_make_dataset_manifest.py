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
