"""Grid search over stimulus/motor constants on the calibration scenes (docs/calibration.md).

Every brain run is compared with a no-brain run of the same scene, because the gait alone drifts.

    uv run python scripts/calibrate.py --grid default --out out/calibration --workers 4
"""

import argparse
import csv
import itertools
import time
from multiprocessing import Pool
from pathlib import Path

from flybrain.config import Config, load_config
from flybrain.connectome import Connectome
from flybrain.loop import ConstantController, make_brain_controller, run_scene
from flybrain.metrics import escape_metrics
from flybrain.recording import read_recording
from flybrain.scene import load_scene

SCENES = Path("scenes/calibration")
GRIDS = {
    "default": {
        "stimulus.theta_dot_0_deg_s": [5, 20],
        "stimulus.theta_dot_sat_deg_s": [100, 200, 300],
        "motor.k_turn": [0.01, 0.02, 0.04],
    },
}
ACCEPT_TURN_DEG = 20.0
ACCEPT_GF_HZ = 100.0
ACCEPT_SLOW_DEG = 5.0
ACCEPT_FRONT_PATH = 1.10

_connectome: Connectome | None = None


def apply(config: Config, overrides: dict[str, float]) -> Config:
    data = config.model_dump()
    for key, value in overrides.items():
        section, name = key.split(".")
        data[section][name] = value
    return Config.model_validate(data)


def config_id(overrides: dict[str, float]) -> str:
    return "_".join(f"{k.split('.')[1]}={v}" for k, v in overrides.items())


def _init_worker(data_dir: str) -> None:
    global _connectome
    _connectome = Connectome.from_files(Path(data_dir))


def _run_brain(job: tuple[dict, str, str]) -> dict:
    overrides, scene_name, out_root = job
    scene = load_scene(SCENES / f"{scene_name}.json")
    cfg = apply(load_config(), overrides)
    out = Path(out_root) / config_id(overrides) / scene_name
    t0 = time.time()
    assert _connectome is not None, "worker not initialised"
    run_scene(scene, cfg, make_brain_controller(scene, cfg, _connectome), out)
    baseline = read_recording(Path(out_root) / "baseline" / scene_name)
    m = escape_metrics(read_recording(out), baseline)
    return {**overrides, "scene": scene_name, **vars(m), "wall_s": round(time.time() - t0, 1)}


def _run_baseline(job: tuple[str, str]) -> None:
    scene_name, out_root = job
    scene = load_scene(SCENES / f"{scene_name}.json")
    cfg = load_config()
    drive = (cfg.motor.base_drive, cfg.motor.base_drive)
    run_scene(scene, cfg, ConstantController(drive), Path(out_root) / "baseline" / scene_name)


def summarize(rows: list[dict], keys: list[str]) -> str:
    by_cfg: dict[tuple, dict[str, dict]] = {}
    for r in rows:
        by_cfg.setdefault(tuple(r[k] for k in keys), {})[r["scene"]] = r
    head = keys + ["turn L", "turn R", "turn front", "turn slow", "path front", "GF L/R", "pass"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for cfg_vals, s in by_cfg.items():
        left, right = s["loom_left_fast"], s["loom_right_fast"]
        front, slow = s["loom_front"], s["slow_far"]
        ok = (
            left["turn_deg"] <= -ACCEPT_TURN_DEG
            and right["turn_deg"] >= ACCEPT_TURN_DEG
            and min(left["gf_peak_hz"], right["gf_peak_hz"]) > ACCEPT_GF_HZ
            and abs(slow["turn_deg"]) < ACCEPT_SLOW_DEG
            and slow["input_peak_hz"] == 0
            and front["path_ratio"] >= ACCEPT_FRONT_PATH
            and all(x["status"] == "complete" for x in (left, right, front, slow))
        )
        cells = [str(v) for v in cfg_vals] + [
            f"{left['turn_deg']:+.1f}",
            f"{right['turn_deg']:+.1f}",
            f"{front['turn_deg']:+.1f}",
            f"{slow['turn_deg']:+.1f}",
            f"{front['path_ratio']:.2f}",
            f"{left['gf_peak_hz']:.0f}/{right['gf_peak_hz']:.0f}",
            "yes" if ok else "no",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="default", choices=sorted(GRIDS))
    ap.add_argument("--out", type=Path, default=Path("out/calibration"))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--data-dir", default="data")
    args = ap.parse_args()

    grid = GRIDS[args.grid]
    keys = list(grid)
    scene_names = sorted(p.stem for p in SCENES.glob("*.json"))
    combos = [dict(zip(keys, vals, strict=True)) for vals in itertools.product(*grid.values())]
    jobs = [(c, s, str(args.out)) for c in combos for s in scene_names]

    with Pool(args.workers) as pool:
        pool.map(_run_baseline, [(s, str(args.out)) for s in scene_names])
    with Pool(args.workers, initializer=_init_worker, initargs=(args.data_dir,)) as pool:
        rows = pool.map(_run_brain, jobs, chunksize=1)

    rows.sort(key=lambda r: ([r[k] for k in keys], r["scene"]))
    with open(args.out / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (args.out / "results.md").write_text(summarize(rows, keys))
    print(summarize(rows, keys))


if __name__ == "__main__":
    main()
