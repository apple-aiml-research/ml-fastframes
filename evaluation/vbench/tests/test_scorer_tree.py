#
# For licensing see accompanying LICENSE file.
# Copyright (C) 2026 Apple Inc. All Rights Reserved.
#
"""CPU tests that the VBench scorer matches the one used for the paper.

The on-disk checks need the scorer package built by setup_scorer.py and are skipped otherwise.
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import protocol  # noqa: E402
import setup_scorer  # noqa: E402
import summarize  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((HERE / "scorer_manifest.json").read_text(encoding="utf-8"))
ORIGINAL_TREE_SHA256 = "78e9ca69a8625dba6413521cf87d92fe88561e4a1da4e90d74f07ec4db0be0c3"


def _tree_hash(files):
    digest = hashlib.sha256()
    for rel in sorted(files, key=lambda path: Path(path).parts):
        digest.update(f"{rel}\0{files[rel]}\n".encode("utf-8"))
    return digest.hexdigest()


def _hashed(rel):
    return rel in ("evaluate.py", "scripts/constant.py") or (rel.startswith("vbench/") and rel.endswith(".py"))


def test_original_tree_hash_from_manifest():
    assert len(MANIFEST["original_tree_files"]) == 177
    assert _tree_hash(MANIFEST["original_tree_files"]) == ORIGINAL_TREE_SHA256 == MANIFEST["original_tree_sha256"]


def test_repository_files_match_manifest():
    vendored = MANIFEST["vendored_files"]
    for rel in ("LICENSE", "evaluate.py", "static_filter.py", "scripts/constant.py"):
        assert protocol.sha256_file(summarize.VBENCH_ROOT / rel) == vendored[rel]


def test_manifest_python_identical_to_original():
    original = MANIFEST["original_tree_files"]
    hashed = {rel: digest for rel, digest in MANIFEST["vendored_files"].items() if _hashed(rel)}
    assert len(hashed) == 130
    assert all(original[rel] == digest for rel, digest in hashed.items())
    assert _tree_hash(hashed) == MANIFEST["vendored_tree_sha256"]


@pytest.mark.skipif(not (summarize.VBENCH_ROOT / "vbench").is_dir(), reason="run setup_scorer.py first")
def test_built_scorer_matches_manifest():
    assert setup_scorer.verify(summarize.VBENCH_ROOT) == len(MANIFEST["vendored_files"])
    assert summarize.scorer_tree_sha256() == MANIFEST["vendored_tree_sha256"]
