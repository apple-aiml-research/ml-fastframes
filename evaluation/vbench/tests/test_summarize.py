#
# For licensing see accompanying LICENSE file.
# Copyright (C) 2026 Apple Inc. All Rights Reserved.
#
"""CPU tests for the VBench score aggregation."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import summarize  # noqa: E402

TABLE1 = json.loads((Path(__file__).parent / "data" / "table1_raw_scores.json").read_text(encoding="utf-8"))
C = summarize.C


def _raw(fraction):
    """Raw scores placing every dimension at ``fraction`` of its normalization range."""
    return {d: C.NORMALIZE_DIC[d]["Min"] + fraction * (C.NORMALIZE_DIC[d]["Max"] - C.NORMALIZE_DIC[d]["Min"])
            for d in C.TASK_INFO}


def test_constants():
    assert len(C.TASK_INFO) == 16
    assert set(C.QUALITY_LIST) | set(C.SEMANTIC_LIST) == set(C.TASK_INFO)
    assert (C.QUALITY_WEIGHT, C.SEMANTIC_WEIGHT) == (4, 1)
    assert C.DIM_WEIGHT["dynamic degree"] == 0.5
    assert sum(C.DIM_WEIGHT.values()) == 15.5


@pytest.mark.parametrize("fraction", [0.0, 0.25, 1.0])
def test_uniform_scores(fraction):
    scores = summarize.aggregate(_raw(fraction))
    for key in ("quality_score", "semantic_score", "total_score"):
        assert scores[key] == pytest.approx(fraction, abs=1e-12)


def test_weighting():
    raw = _raw(0.0)
    raw["dynamic degree"] = 1.0  # quality weight 0.5 of 6.5
    raw["scene"] = C.NORMALIZE_DIC["scene"]["Max"]  # semantic weight 1 of 9
    scores = summarize.aggregate(raw)
    assert scores["quality_score"] == pytest.approx(0.5 / 6.5)
    assert scores["semantic_score"] == pytest.approx(1 / 9)
    assert scores["total_score"] == pytest.approx((4 * 0.5 / 6.5 + 1 / 9) / 5)
    assert scores["normalized_scores"]["scene"] == pytest.approx(1.0)


@pytest.mark.parametrize("name", list(TABLE1["rows"]))
def test_table1(name):
    row = TABLE1["rows"][name]
    scores = summarize.aggregate(row["raw_scores"])
    for key in ("total_score", "quality_score", "semantic_score"):
        assert scores[key] == row[key]  # bitwise, as recorded
    reported = [round(100 * scores[k], 2) for k in ("total_score", "quality_score", "semantic_score")]
    assert reported == row["paper_total_quality_semantic"]


def test_load_result(tmp_path):
    payload = {d.replace(" ", "_"): [0.5, []] for d in C.TASK_INFO if d != "temporal flickering"}
    path = tmp_path / "results_eval_results.json"
    path.write_text(json.dumps(payload))
    raw = summarize.load_result(path, summarize.NON_TEMPORAL)
    assert len(raw) == 15 and "subject consistency" in raw
    del payload["scene"]
    path.write_text(json.dumps(payload))
    with pytest.raises(RuntimeError, match="dimension set mismatch"):
        summarize.load_result(path, summarize.NON_TEMPORAL)
