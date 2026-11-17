#
# For licensing see accompanying LICENSE file.
# Copyright (C) 2026 Apple Inc. All Rights Reserved.
#
"""CPU tests for the VBench sampling protocol."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import protocol  # noqa: E402

UKIYO = "A beautiful coastal beach in spring, waves lapping on sand by Hokusai, in the style of Ukiyo"


@pytest.fixture(scope="module")
def suite():
    return protocol.load_suite()


@pytest.fixture(scope="module")
def jobs(suite):
    return protocol.build_sample_specs(suite)


def test_counts(suite, jobs):
    assert suite.protocol_identifier == protocol.EXTENDED_PROTOCOL
    assert suite.rows == 946
    assert len(suite.prompts) == 944
    assert len(suite.temporal_prompts) == 75
    assert len(jobs) == 6_220
    assert len({job.filename for job in jobs}) == 6_220
    assert sum(job.temporal_flickering for job in jobs) == 75 * 25
    assert sum(not job.temporal_flickering for job in jobs) == 869 * 5
    # Scored slots: 5 per prompt, temporal ones filled by the static filter.
    assert len(suite.prompts) * protocol.BASE_SAMPLES == protocol.EXPECTED_SCORING_VIDEOS


def test_seed_map(suite, jobs):
    for job in jobs:
        assert job.seed == job.prompt_ordinal * 25 + job.sample_index
        assert 0 <= job.sample_index < (25 if job.temporal_flickering else 5)
    assert len({job.seed for job in jobs}) == 6_220
    assert protocol.seed_map_fingerprint(jobs) == protocol.EXPECTED_SEED_MAP_SHA256
    assert protocol.protocol_summary(suite)["seed_map_sha256"] == protocol.EXPECTED_SEED_MAP_SHA256
    # The original-prompt protocol shares filenames and seeds.
    raw_jobs = protocol.build_sample_specs(protocol.load_prompt_suite())
    assert [(j.filename, j.seed) for j in raw_jobs] == [(j.filename, j.seed) for j in jobs]


def test_prompt_pairing(suite, jobs):
    assert suite.prompt_pair_sha256 == protocol.EXPECTED_RESOLVED_PROMPT_PAIR_SHA256
    rows = dict(zip(suite.prompts, suite.resolved_source_rows_one_based))
    assert rows[UKIYO] == 749
    assert rows["The bund Shanghai, oil painting"] == 747
    extended = protocol._prompt_lines(protocol.DEFAULT_EXTENDED_PROMPTS)
    for prompt, conditioning in zip(suite.prompts, suite.conditioning_prompts):
        assert conditioning == extended[rows[prompt] - 1]
    assert all(job.filename == f"{job.prompt}-{job.sample_index}.mp4" for job in jobs)
    assert sum(job.conditioning_prompt != job.prompt for job in jobs) > 6_000


def test_causvid_conditioning(jobs):
    suite = protocol.load_suite(protocol.CAUSVID_PROTOCOL)
    assert suite.prompt_pair_sha256 == protocol.CONDITIONING[protocol.CAUSVID_PROTOCOL][2]
    causvid = protocol.build_sample_specs(suite)
    # Same videos and seeds as the other models; only the conditioning text differs.
    assert [(j.filename, j.seed) for j in causvid] == [(j.filename, j.seed) for j in jobs]
    assert sum(a.conditioning_prompt != b.conditioning_prompt for a, b in zip(causvid, jobs)) > 6_000
    assert protocol.protocol_summary(suite)["seed_map_sha256"] == protocol.EXPECTED_SEED_MAP_SHA256


def test_pinned_prompt_files():
    assert protocol.sha256_file(protocol.DEFAULT_FULL_INFO) == protocol.EXPECTED_FULL_INFO_SHA256
    assert protocol.sha256_file(protocol.DEFAULT_ORIGINAL_PROMPTS) == protocol.EXPECTED_ORIGINAL_PROMPTS_SHA256
    for path, sha256, _ in protocol.CONDITIONING.values():
        assert protocol.sha256_file(path) == sha256


def test_rejects_modified_prompts(tmp_path):
    modified = tmp_path / "all_dimension_extended.txt"
    modified.write_bytes(protocol.DEFAULT_EXTENDED_PROMPTS.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="hash changed"):
        protocol.load_suite(extended_prompt_path=modified)


def test_filtered_names(suite):
    temporal = [p for p in suite.prompts if p in suite.temporal_prompts]
    selection = {p: [{"output_filename": f"{p}-{i}.mp4"} for i in range(5 if k else 3)]
                 for k, p in enumerate(temporal)}
    contract = {"selection_by_prompt": selection, "output_video_count": 74 * 5 + 3}
    assert len(protocol.expected_filtered_names(suite, contract)) == 373
    selection[temporal[0]] = [{"output_filename": f"{temporal[0]}-1.mp4"}]
    with pytest.raises(RuntimeError, match="sequence"):
        protocol.expected_filtered_names(suite, contract)


def test_faststart_box_order(tmp_path):
    def box(kind, payload=b""):
        return (8 + len(payload)).to_bytes(4, "big") + kind + payload

    good = tmp_path / "good.mp4"
    good.write_bytes(box(b"ftyp", b"isom") + box(b"moov", b"\0" * 8) + box(b"mdat", b"\0" * 16))
    assert protocol._top_level_boxes(good) == ["ftyp", "moov", "mdat"]
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(box(b"ftyp") + box(b"mdat", b"\0" * 4) + box(b"moov"))
    boxes = protocol._top_level_boxes(bad)
    assert boxes.index("moov") > boxes.index("mdat")


def test_mp4_write_and_probe(tmp_path):
    sps, pps = bytes([0x67, 100, 0, 30, 0xAC, 0xD9]), bytes([0x68, 0xEB, 0xE3, 0xCB])
    idr, inter = bytes([0x65, 0x88, 0x84]), bytes([0x41, 0x9A, 0x02, 0x03])
    units = [[sps, pps, idr]] + [[inter]] * 40 + [[sps, pps, idr]] + [[inter]] * 39
    path = protocol.mp4.write_h264(tmp_path / "v.mp4", units, width=832, height=480, fps=16, sps=sps, pps=pps)
    assert protocol._top_level_boxes(path) == ["ftyp", "moov", "mdat"]
    assert protocol.mp4.probe(path) == {"codec": "h264", "width": 832, "height": 480, "frames": 81, "fps": 16}
    track = protocol.mp4.read_h264(path)
    assert (track.sps, track.pps, track.sync) == ([sps], [pps], [0, 41])
    expected = [[idr]] + [[inter]] * 40 + [[idr]] + [[inter]] * 39  # parameter sets live in avcC
    assert [track.nal_units(sample) for sample in track.samples()] == expected
    umask = os.umask(0)
    os.umask(umask)
    assert path.stat().st_mode & 0o777 == 0o666 & ~umask


def test_write_faststart_video(tmp_path):
    np = pytest.importorskip("numpy")
    from fastframes import openh264, video

    try:
        openh264.load_library()
    except RuntimeError:
        pytest.skip("OpenH264 2.7 could not be loaded or downloaded")
    t, y, x = np.meshgrid(np.arange(81), np.arange(480), np.arange(832), indexing="ij")
    frames = np.stack([(x + 4 * t) % 256, (y + 2 * t) % 256, (x + y) // 6 % 256], axis=-1).astype(np.uint8)
    result = protocol.write_faststart_video(tmp_path / "v.mp4", frames)
    assert result["faststart"] and result["frames"] == 81 and result["sha256"]
    assert protocol.write_faststart_video(tmp_path / "w.mp4", frames)["sha256"] == result["sha256"]  # repeatable
    decoded = video.read_video(tmp_path / "v.mp4")
    mse = np.mean((decoded.astype(np.float64) - frames) ** 2)
    assert 10 * np.log10(255**2 / mse) > 35
    assert np.array_equal(video.read_video(tmp_path / "v.mp4", 50, 5), decoded[50:55])
    assert video.sps_color(protocol.mp4.read_h264(tmp_path / "v.mp4").sps[0]) == (6, False)  # BT.601 limited
    with pytest.raises(ValueError, match="qp"):
        video.save_video(tmp_path / "x.mp4", frames[:2], qp=10)


def test_jobs_cli(tmp_path, monkeypatch):
    output = tmp_path / "jobs.jsonl"
    monkeypatch.setattr(sys, "argv", ["protocol.py", "jobs", "--output", str(output)])
    assert protocol.main() == 0
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 6_220
    assert rows[0]["seed"] == 0 and rows[-1]["seed"] == 943 * 25 + rows[-1]["sample_index"]
