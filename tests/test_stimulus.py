import math

import numpy as np
import pytest

from flybrain.config import StimulusConfig
from flybrain.scene import Threat
from flybrain.stimulus import LoomingEncoder, eye_weights, threat_position, visual_angle

EYES = dict(
    eye_left=np.array([0, 0.2, 1.0]),
    eye_right=np.array([0, -0.2, 1.0]),
    head=np.array([0, 0, 1.0]),
    forward=np.array([1.0, 0, 0]),
)


def test_eye_weights():
    assert eye_weights(math.pi / 2, 20) == pytest.approx((1.0, 0.0))
    assert eye_weights(0.0, 20) == pytest.approx((0.5, 0.5))
    assert eye_weights(-math.pi / 2, 20) == pytest.approx((0.0, 1.0))
    assert eye_weights(math.pi, 20) == pytest.approx((0.5, 0.5))  # directly behind


def test_visual_angle_clamps_at_contact():
    assert visual_angle(4, 0.0) == pytest.approx(math.pi)
    assert visual_angle(4, 2.0) == pytest.approx(math.pi)
    assert visual_angle(1, 1e6) == pytest.approx(2e-6, rel=1e-3)


def test_threat_position_constant_speed_and_stop():
    th = Threat(size_mm=8, speed_mm_s=10, path=[(0, 0, 0), (10, 0, 0), (10, 10, 0)])
    assert threat_position(th, 0.5) == pytest.approx([5, 0, 0])
    assert threat_position(th, 1.5) == pytest.approx([10, 5, 0])
    assert threat_position(th, 99) == pytest.approx([10, 10, 0])


def test_fast_approach_from_left_drives_left_eye_only():
    th = Threat(size_mm=8, speed_mm_s=200, path=[(0, 30, 2), (0, 1, 2)])
    enc = LoomingEncoder(StimulusConfig(), th)
    out = [enc.rates(t, **EYES) for t in np.arange(0, 0.14, 0.02)]
    assert out[0] == (0.0, 0.0)
    assert max(left for left, _ in out) > 100
    assert max(right for _, right in out) < 1e-6


def test_slow_distant_threat_no_input():
    th = Threat(size_mm=2, speed_mm_s=1, path=[(50, 0, 2), (40, 0, 2)])
    enc = LoomingEncoder(StimulusConfig(), th)
    assert all(enc.rates(t, **EYES) == (0.0, 0.0) for t in np.arange(0, 1, 0.02))


def test_threat_through_fly_gives_finite_rates():
    th = Threat(size_mm=8, speed_mm_s=100, path=[(0, 5, 1), (0, -5, 1)])
    enc = LoomingEncoder(StimulusConfig(), th)
    for t in np.arange(0, 0.2, 0.02):
        left, right = enc.rates(t, **EYES)
        assert math.isfinite(left) and math.isfinite(right)
        assert 0 <= left <= 150 and 0 <= right <= 150


def test_last_theta_reported_in_degrees():
    th = Threat(size_mm=4, speed_mm_s=1, path=[(0, 4.2, 1), (0, 100, 1)])
    enc = LoomingEncoder(StimulusConfig(), th)
    enc.rates(0.0, **EYES)
    # left eye at distance 4.0 from the centre of a radius-2 threat: 2*atan(2/4) = 53.13 deg
    assert enc.last_theta_deg[0] == pytest.approx(53.13, abs=0.05)
