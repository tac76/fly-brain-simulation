from pathlib import Path

from flybrain.config import load_config
from flybrain.scene import load_scene

CAL = Path("scenes/calibration")


def test_calibration_scenes_valid():
    files = sorted(CAL.glob("*.json"))
    expected = {"loom_left_fast", "loom_right_fast", "loom_front", "slow_far"}
    assert {f.stem for f in files} == expected
    for f in files:
        load_scene(f).validate_against(load_config())


def test_right_is_mirror_of_left():
    left = load_scene(CAL / "loom_left_fast.json")
    right = load_scene(CAL / "loom_right_fast.json")
    assert right.shadow.path == [(x, -y, z) for x, y, z in left.shadow.path]
    assert right.shadow.speed_mm_s == left.shadow.speed_mm_s
