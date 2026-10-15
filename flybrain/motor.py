"""Descending-neuron activity -> the two walking drives of FlyGym's HybridTurningController.

Hand-built mapping (not part of the brain model):
- Steering: DNa02 activity on one side turns the fly to that side. In the turning controller the
  side with the smaller drive is the inside of the turn, so right-side DNa activity lowers the
  right drive.
- Escape: giant-fiber (DNp01) activity speeds the fly up, saturating at boost_max.
- With a silent brain the fly walks straight at base_drive (a default, not a brain decision).
"""

import math
from dataclasses import dataclass

import numpy as np

from flybrain.config import MotorConfig


@dataclass
class DNRates:
    dna_left: float  # DNa01 + DNa02, left side, Hz
    dna_right: float  # DNa01 + DNa02, right side, Hz
    gf: float  # mean DNp01 left/right, Hz


class MotorMapper:
    def __init__(self, cfg: MotorConfig, interval_ms: float = 20):
        self.cfg = cfg
        self.alpha = 1.0 - math.exp(-interval_ms / cfg.tau_ms)
        self.smoothed = DNRates(0.0, 0.0, 0.0)

    def update(self, rates: DNRates) -> np.ndarray:
        a, s, cfg = self.alpha, self.smoothed, self.cfg
        s.dna_left += a * (rates.dna_left - s.dna_left)
        s.dna_right += a * (rates.dna_right - s.dna_right)
        s.gf += a * (rates.gf - s.gf)

        turn = cfg.k_turn * (s.dna_right - s.dna_left)
        boost = cfg.boost_max * math.tanh(cfg.k_gf * s.gf)
        speed = cfg.base_drive * (1.0 + boost)
        drive = np.array([speed + turn / 2.0, speed - turn / 2.0])
        return np.clip(drive, cfg.drive_min, cfg.drive_max)
