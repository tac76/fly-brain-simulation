"""Write small recordings with known values for the viewer's unit and e2e tests.

    uv run python scripts/make_viewer_fixtures.py
"""

from pathlib import Path

import numpy as np

from flybrain.recording import RecordingWriter

OUT = Path("viewer/tests/fixtures")


def main() -> None:
    w = RecordingWriter(OUT / "tiny", {"seed": 1, "scene": {"shadow": {"size_mm": 8}}}, ["A", "B"])
    for i in range(3):
        poses = np.zeros((2, 7), np.float32)
        poses[:, 0] = i  # x = frame index
        poses[1, 1] = 10 + i  # part B: y = 10 + frame
        poses[:, 3] = 1.0  # identity quaternion (w, x, y, z)
        w.append(poses, np.array([i, i + 100], np.uint32), {"gf_hz": float(i * 50)})
    w.close("complete")

    w = RecordingWriter(OUT / "aborted", {"seed": 1}, ["A"])
    pose = np.array([[0, 0, 1, 1, 0, 0, 0]], np.float32)
    w.append(pose, np.array([], np.uint32), {})
    w.close("aborted", reason="flipped")
    print("fixtures written to", OUT)


if __name__ == "__main__":
    main()
