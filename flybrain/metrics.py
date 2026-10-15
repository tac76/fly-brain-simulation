"""Escape metrics: compare a brain run with a no-brain run of the same scene and seed.

The gait alone drifts a few degrees, so a turn only counts relative to that baseline.
"""

import math
from dataclasses import dataclass

import numpy as np

from flybrain.recording import Recording


def _thorax_xy(rec: Recording) -> np.ndarray:
    i = rec.meta["part_names"].index("Thorax")
    return rec.poses[:, i, :2].astype(float)


def walk_heading_deg(rec: Recording, start: int, end: int) -> float:
    """Direction of thorax displacement from frame start to frame end, in degrees."""
    d = _thorax_xy(rec)[end] - _thorax_xy(rec)[start]
    return math.degrees(math.atan2(d[1], d[0]))


def _wrap(deg: float) -> float:
    """Wrap to (-180, 180]."""
    w = (deg + 180.0) % 360.0 - 180.0
    return 180.0 if w == -180.0 else w


@dataclass
class EscapeMetrics:
    turn_deg: float  # brain minus baseline walking direction in the late window; + = left
    path_ratio: float  # brain path length / baseline path length over common frames
    gf_peak_hz: float
    input_peak_hz: float
    status: str


def escape_metrics(brain: Recording, baseline: Recording) -> EscapeMetrics:
    n = min(brain.meta["n_frames"], baseline.meta["n_frames"])
    start, end = n // 2, n - 1
    turn = _wrap(walk_heading_deg(brain, start, end) - walk_heading_deg(baseline, start, end))

    def path(rec: Recording) -> float:
        xy = _thorax_xy(rec)[:n]
        return float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum())

    base_path = path(baseline)
    s = brain.signals
    inputs = list(s.get("input_left_hz", [])) + list(s.get("input_right_hz", []))
    return EscapeMetrics(
        turn_deg=turn,
        path_ratio=path(brain) / base_path if base_path > 0 else float("nan"),
        gf_peak_hz=float(max(s.get("gf_hz", [0.0]) or [0.0])),
        input_peak_hz=float(max(inputs or [0.0])),
        status=brain.meta["status"],
    )
