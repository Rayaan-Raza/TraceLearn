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
