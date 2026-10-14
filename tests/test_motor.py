import math

import pytest

from flybrain.config import MotorConfig
from flybrain.motor import DNRates, MotorMapper


def test_silent_brain_walks_straight_at_base():
    m = MotorMapper(MotorConfig())
    assert m.update(DNRates(0, 0, 0)) == pytest.approx([0.7, 0.7])


def test_right_dna_activity_turns_right():
    m = MotorMapper(MotorConfig())
    for _ in range(20):
        d = m.update(DNRates(0, 60, 0))
    assert d[1] < d[0]


def test_giant_fiber_boosts_speed_and_saturates():
    m = MotorMapper(MotorConfig())
    for _ in range(50):
        d = m.update(DNRates(0, 0, 1e6))
    assert d == pytest.approx([0.7 * 1.8, 0.7 * 1.8], rel=1e-3)


def test_drives_are_clipped():
    m = MotorMapper(MotorConfig(k_turn=1.0))
    for _ in range(50):
        d = m.update(DNRates(0, 1000, 0))
    assert d[0] == 1.5 and d[1] == 0.0


def test_ema_first_step():
    m = MotorMapper(MotorConfig())
    m.update(DNRates(0, 100, 0))
    assert m.smoothed.dna_right == pytest.approx(100 * (1 - math.exp(-20 / 50)))
