"""Looming stimulus: scene geometry -> Poisson input rate for each eye's looming detectors.

Hand-built encoding (not part of the brain model): the rate grows with how fast the object's
apparent size expands, and is split between the eyes by the object's direction.
"""

import math

import numpy as np

from flybrain.config import StimulusConfig
from flybrain.scene import Threat


def threat_position(threat: Threat, t_s: float) -> np.ndarray:
    """Position along the polyline path at constant speed; stays at the last point after arrival."""
    pts = np.asarray(threat.path, dtype=float)
    remaining = max(t_s, 0.0) * threat.speed_mm_s
    for a, b in zip(pts[:-1], pts[1:], strict=True):
        seg = float(np.linalg.norm(b - a))
        if remaining <= seg:
            return a + (b - a) * (remaining / seg)
        remaining -= seg
    return pts[-1].copy()


def visual_angle(radius_mm: float, distance_mm: float) -> float:
    """Apparent size in radians, 2*atan(r/d); pi when the eye is at or inside the object."""
    if distance_mm <= radius_mm:
        return math.pi
    return 2.0 * math.atan(radius_mm / distance_mm)


def eye_weights(azimuth_rad: float, overlap_deg: float) -> tuple[float, float]:
    """Share of (left, right) eye; azimuth positive = fly's left. Blends in front and behind."""
    w_left = 0.5 + math.sin(azimuth_rad) / (2.0 * math.sin(math.radians(overlap_deg)))
    w_left = min(max(w_left, 0.0), 1.0)
    return w_left, 1.0 - w_left


class LoomingEncoder:
    def __init__(self, cfg: StimulusConfig, threat: Threat, interval_s: float = 0.02):
        self.cfg = cfg
        self.threat = threat
        self.interval_s = interval_s
        self.radius = threat.size_mm / 2.0
        self._theta_prev: tuple[float, float] | None = None
        self.last_theta_deg: tuple[float, float] = (0.0, 0.0)

    def rates(
        self,
        t_s: float,
        eye_left: np.ndarray,
        eye_right: np.ndarray,
        head: np.ndarray,
        forward: np.ndarray,
    ) -> tuple[float, float]:
        cfg = self.cfg
        pos = threat_position(self.threat, t_s)
        thetas = tuple(
            visual_angle(self.radius, float(np.linalg.norm(pos - np.asarray(eye))))
            for eye in (eye_left, eye_right)
        )
        prev = self._theta_prev or thetas
        self._theta_prev = thetas
        self.last_theta_deg = (math.degrees(thetas[0]), math.degrees(thetas[1]))

        v = (pos - np.asarray(head))[:2]
        f = np.asarray(forward, dtype=float)[:2]
        left_axis = np.array([-f[1], f[0]])
        azimuth = math.atan2(float(v @ left_axis), float(v @ f))
        weights = eye_weights(azimuth, cfg.overlap_deg)

        span = math.radians(cfg.theta_dot_sat_deg_s - cfg.theta_dot_0_deg_s)
        out = []
        for theta, theta_prev, w in zip(thetas, prev, weights, strict=True):
            if theta <= math.radians(cfg.theta_min_deg):
                out.append(0.0)
                continue
            theta_dot = (theta - theta_prev) / self.interval_s
            drive = (theta_dot - math.radians(cfg.theta_dot_0_deg_s)) / span
            out.append(cfg.r_max_hz * min(max(drive, 0.0), 1.0) * w)
        return out[0], out[1]
