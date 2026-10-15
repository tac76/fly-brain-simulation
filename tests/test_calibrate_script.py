import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("calibrate", Path("scripts/calibrate.py"))
cal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cal)


def _row(scene, turn, path=1.0, gf=200.0, inp=100.0, seed=1):
    return {"k": 1, "seed": seed, "scene": scene, "turn_deg": turn, "path_ratio": path,
            "gf_peak_hz": gf, "input_peak_hz": inp, "status": "complete"}


def test_calibration_scene_seed_override():
    assert cal.load_cal_scene("loom_left_fast", seed=3).seed == 3


def test_summary_shows_three_decimals_and_failed_criteria():
    rows = [
        _row("loom_left_fast", -30), _row("loom_right_fast", 30),
        _row("loom_front", 0, path=1.0967), _row("slow_far", 0, inp=0),
    ]
    md = cal.summarize(rows, ["k"])
    assert "1.097" in md and "front path" in md and "| no |" in md


def test_summary_one_row_per_seed():
    rows = []
    for seed in (1, 2):
        rows += [_row("loom_left_fast", -30, seed=seed), _row("loom_right_fast", 30, seed=seed),
                 _row("loom_front", 0, path=1.2, seed=seed), _row("slow_far", 0, inp=0, seed=seed)]
    md = cal.summarize(rows, ["k"])
    assert md.count("| yes |") == 2
