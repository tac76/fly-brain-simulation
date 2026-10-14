import json

import numpy as np
import pytest

from flybrain.recording import FORMAT_VERSION, RecordingWriter, read_recording


def _write(path, n_frames=3, status="complete", reason=None):
    w = RecordingWriter(path, {"seed": 1}, ["a", "b"])
    for i in range(n_frames):
        w.append(
            np.full((2, 7), i, np.float32),
            np.array([i, i + 10], np.uint32),
            {"drive_left": 0.5, "theta": [1.0, 2.0]},
        )
    w.close(status, reason=reason)


def test_round_trip(tmp_path):
    _write(tmp_path)
    r = read_recording(tmp_path)
    assert r.meta["n_frames"] == 3 and r.poses.shape == (3, 2, 7)
    assert r.meta["format_version"] == FORMAT_VERSION and r.meta["part_names"] == ["a", "b"]
    assert list(r.frame_spikes(2)) == [2, 12] and r.signals["drive_left"] == [0.5] * 3
    assert r.signals["theta"] == [[1.0, 2.0]] * 3
    assert r.meta["seed"] == 1


def test_aborted_partial_recording_readable(tmp_path):
    w = RecordingWriter(tmp_path, {}, ["a"])
    w.append(np.zeros((1, 7), np.float32), np.array([], np.uint32), {})
    w.close("aborted", reason="flipped")
    r = read_recording(tmp_path)
    assert r.meta["status"] == "aborted" and r.meta["reason"] == "flipped"
    assert r.meta["n_frames"] == 1 and len(r.frame_spikes(0)) == 0


def test_rejects_unknown_version(tmp_path):
    _write(tmp_path)
    meta = json.loads((tmp_path / "meta.json").read_text())
    meta["format_version"] = 99
    (tmp_path / "meta.json").write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="format_version"):
        read_recording(tmp_path)


def test_identical_input_gives_identical_bytes(tmp_path):
    _write(tmp_path / "a")
    _write(tmp_path / "b")
    for f in ("meta.json", "body.bin", "spikes.bin", "signals.json"):
        assert (tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes()


def test_wrong_pose_shape_rejected(tmp_path):
    w = RecordingWriter(tmp_path, {}, ["a", "b"])
    with pytest.raises(ValueError, match="poses"):
        w.append(np.zeros((3, 7), np.float32), np.array([], np.uint32), {})
