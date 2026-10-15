import math

import numpy as np
import pytest

from flybrain.metrics import escape_metrics, walk_heading_deg
from flybrain.recording import RecordingWriter, read_recording


def _rec(path, xy, status="complete", gf=None):
    w = RecordingWriter(path, {}, ["Thorax"])
    for i, (x, y) in enumerate(xy):
        pose = np.array([[x, y, 1.0, 1, 0, 0, 0]], np.float32)
        sig = {"gf_hz": gf[i], "input_left_hz": 0.0, "input_right_hz": 0.0} if gf else {}
        w.append(pose, np.array([], np.uint32), sig)
    w.close(status, reason="flipped" if status == "aborted" else None)
    return read_recording(path)


def _straight(n, angle_deg=0.0, step=1.0):
    a = math.radians(angle_deg)
    return [(i * step * math.cos(a), i * step * math.sin(a)) for i in range(n)]


def test_identical_runs_give_zero_turn(tmp_path):
    a = _rec(tmp_path / "a", _straight(10))
    b = _rec(tmp_path / "b", _straight(10))
    m = escape_metrics(a, b)
    assert m.turn_deg == pytest.approx(0) and m.path_ratio == pytest.approx(1)
    assert m.status == "complete"


def test_bend_to_negative_y_is_negative_turn(tmp_path):
    bent = _straight(5) + [(4 + i, -i) for i in range(1, 6)]
    m = escape_metrics(_rec(tmp_path / "a", bent), _rec(tmp_path / "b", _straight(10)))
    assert m.turn_deg < -20


def test_turn_wraps_around_180(tmp_path):
    a = _rec(tmp_path / "a", _straight(10, 179))
    b = _rec(tmp_path / "b", _straight(10, -179))
    assert escape_metrics(a, b).turn_deg == pytest.approx(-2, abs=1e-3)


def test_aborted_brain_run_uses_common_frames(tmp_path):
    a = _rec(tmp_path / "a", _straight(6, step=2.0), status="aborted")
    b = _rec(tmp_path / "b", _straight(10))
    m = escape_metrics(a, b)
    assert m.status == "aborted" and m.path_ratio == pytest.approx(2)


def test_peaks_from_signals(tmp_path):
    a = _rec(tmp_path / "a", _straight(4), gf=[0, 120.0, 30, 0])
    m = escape_metrics(a, _rec(tmp_path / "b", _straight(4)))
    assert m.gf_peak_hz == 120 and m.input_peak_hz == 0


def test_walk_heading(tmp_path):
    r = _rec(tmp_path / "a", _straight(5, 90))
    assert walk_heading_deg(r, 0, 4) == pytest.approx(90)
