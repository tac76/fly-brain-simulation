"""Recording format v1: one folder per run (layout in docs/recording-format.md).

meta.json     run metadata, part names, status
body.bin      float32 little-endian, n_frames x n_parts x 7 (x, y, z, qw, qx, qy, qz)
spikes.bin    uint32 little-endian: n_frames + 1 offsets, then all spiking neuron indices
signals.json  {name: [value per frame]}
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

FORMAT_VERSION = 1
FPS = 50


def _clean(value: Any) -> Any:
    """Plain-Python, rounded values so JSON output is compact and byte-stable."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple | np.ndarray):
        return [_clean(v) for v in value]
    if isinstance(value, bool | np.bool_):
        return bool(value)
    if isinstance(value, int | np.integer):
        return int(value)
    if isinstance(value, float | np.floating):
        return round(float(value), 6)
    return value


def _dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(_clean(data), sort_keys=True, separators=(",", ":")) + "\n")


class RecordingWriter:
    def __init__(self, out_dir: Path, meta: dict, part_names: list[str]):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.meta = dict(meta)
        self.part_names = list(part_names)
        self._poses: list[np.ndarray] = []
        self._spikes: list[np.ndarray] = []
        self._signals: list[dict] = []

    def append(self, poses: np.ndarray, spikes: np.ndarray, signals: dict) -> None:
        poses = np.asarray(poses, dtype="<f4")
        if poses.shape != (len(self.part_names), 7):
            expected = (len(self.part_names), 7)
            raise ValueError(f"poses must have shape {expected}, got {poses.shape}")
        self._poses.append(poses)
        self._spikes.append(np.asarray(spikes, dtype="<u4"))
        self._signals.append(dict(signals))

    def close(
        self,
        status: Literal["complete", "aborted"],
        reason: str | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        n = len(self._poses)
        body = np.stack(self._poses) if n else np.zeros((0, len(self.part_names), 7), "<f4")
        (self.out_dir / "body.bin").write_bytes(body.astype("<f4").tobytes())

        lengths = np.array([len(s) for s in self._spikes], dtype=np.int64)
        offsets = np.zeros(n + 1, dtype="<u4")
        offsets[1:] = np.cumsum(lengths)
        indices = np.concatenate(self._spikes) if n else np.zeros(0, "<u4")
        spikes = offsets.tobytes() + indices.astype("<u4").tobytes()
        (self.out_dir / "spikes.bin").write_bytes(spikes)

        keys = sorted({k for frame in self._signals for k in frame})
        _dump(self.out_dir / "signals.json", {k: [f.get(k) for f in self._signals] for k in keys})

        meta = {
            **self.meta,
            "format_version": FORMAT_VERSION,
            "fps": FPS,
            "n_frames": n,
            "n_parts": len(self.part_names),
            "part_names": self.part_names,
            "status": status,
            "reason": reason,
            "warnings": list(warnings or []),
        }
        _dump(self.out_dir / "meta.json", meta)


@dataclass
class Recording:
    meta: dict
    poses: np.ndarray  # (n_frames, n_parts, 7) float32
    spike_offsets: np.ndarray  # (n_frames + 1,) uint32
    spike_indices: np.ndarray  # uint32
    signals: dict

    def frame_spikes(self, i: int) -> np.ndarray:
        return self.spike_indices[self.spike_offsets[i] : self.spike_offsets[i + 1]]


def read_recording(path: Path) -> Recording:
    path = Path(path)
    meta = json.loads((path / "meta.json").read_text())
    if meta.get("format_version") != FORMAT_VERSION:
        raise ValueError(
            f"unsupported format_version {meta.get('format_version')!r} "
            f"(this reader supports {FORMAT_VERSION})"
        )
    n, parts = meta["n_frames"], meta["n_parts"]
    poses = np.frombuffer((path / "body.bin").read_bytes(), dtype="<f4").reshape(n, parts, 7)
    raw = np.frombuffer((path / "spikes.bin").read_bytes(), dtype="<u4")
    signals = json.loads((path / "signals.json").read_text())
    return Recording(meta, poses, raw[: n + 1], raw[n + 1 :], signals)
