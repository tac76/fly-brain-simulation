"""Grid search over stimulus/motor constants on the calibration scenes (docs/calibration.md).

Every brain run is compared with a no-brain run of the same scene, because the gait alone drifts.

    uv run python scripts/calibrate.py --grid default --out out/calibration --workers 4
    uv run python scripts/calibrate.py --grid selected --seeds 1,2,3 --out out/robustness
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
    # robustness check: the selected config and the runner-up, on several seeds
    "selected": {
        "stimulus.theta_dot_0_deg_s": [5, 20],
        "stimulus.theta_dot_sat_deg_s": [300, 200],
        "motor.k_turn": [0.02, 0.04],
    },
}
PAIRED_GRIDS = {"selected"}  # values are zipped (one config per index), not crossed
ACCEPT_TURN_DEG = 20.0
ACCEPT_GF_HZ = 100.0
ACCEPT_SLOW_DEG = 5.0
ACCEPT_FRONT_PATH = 1.10

_connectome: Connectome | None = None


def load_cal_scene(name: str, seed: int | None = None):
    scene = load_scene(SCENES / f"{name}.json")
    return scene if seed is None else scene.model_copy(update={"seed": seed})


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


def _run_brain(job: tuple[dict, str, int, str]) -> dict:
    overrides, scene_name, seed, out_root = job
    scene = load_cal_scene(scene_name, seed)
    cfg = apply(load_config(), overrides)
    out = Path(out_root) / f"seed{seed}" / config_id(overrides) / scene_name
    t0 = time.time()
    assert _connectome is not None, "worker not initialised"
    run_scene(scene, cfg, make_brain_controller(scene, cfg, _connectome), out)
    baseline = read_recording(Path(out_root) / f"seed{seed}" / "baseline" / scene_name)
    m = escape_metrics(read_recording(out), baseline)
    wall = round(time.time() - t0, 1)
    return {**overrides, "seed": seed, "scene": scene_name, **vars(m), "wall_s": wall}


def _run_baseline(job: tuple[str, int, str]) -> None:
    scene_name, seed, out_root = job
    cfg = load_config()
    drive = (cfg.motor.base_drive, cfg.motor.base_drive)
    out = Path(out_root) / f"seed{seed}" / "baseline" / scene_name
    run_scene(load_cal_scene(scene_name, seed), cfg, ConstantController(drive), out)


def failed_criteria(s: dict[str, dict]) -> list[str]:
    left, right = s["loom_left_fast"], s["loom_right_fast"]
    front, slow = s["loom_front"], s["slow_far"]
    checks = {
        "turn L": left["turn_deg"] <= -ACCEPT_TURN_DEG,
        "turn R": right["turn_deg"] >= ACCEPT_TURN_DEG,
        "GF": min(left["gf_peak_hz"], right["gf_peak_hz"]) > ACCEPT_GF_HZ,
        "slow": abs(slow["turn_deg"]) < ACCEPT_SLOW_DEG and slow["input_peak_hz"] == 0,
        "front path": front["path_ratio"] >= ACCEPT_FRONT_PATH,
        "aborted": all(x["status"] == "complete" for x in (left, right, front, slow)),
    }
    return [name for name, ok in checks.items() if not ok]


def summarize(rows: list[dict], keys: list[str]) -> str:
    by_cfg: dict[tuple, dict[str, dict]] = {}
    for r in rows:
        by_cfg.setdefault(tuple(r[k] for k in keys) + (r["seed"],), {})[r["scene"]] = r
    head = keys + ["seed", "turn L", "turn R", "turn front", "turn slow", "path front", "GF L/R"]
    head += ["pass", "failed"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for cfg_vals, s in by_cfg.items():
        left, right = s["loom_left_fast"], s["loom_right_fast"]
        front, slow = s["loom_front"], s["slow_far"]
        failed = failed_criteria(s)
        cells = [str(v) for v in cfg_vals] + [
            f"{left['turn_deg']:+.1f}",
            f"{right['turn_deg']:+.1f}",
            f"{front['turn_deg']:+.1f}",
            f"{slow['turn_deg']:+.1f}",
            f"{front['path_ratio']:.3f}",
            f"{left['gf_peak_hz']:.0f}/{right['gf_peak_hz']:.0f}",
            "no" if failed else "yes",
            ", ".join(failed) or "-",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="default", choices=sorted(GRIDS))
    ap.add_argument("--out", type=Path, default=Path("out/calibration"))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--seeds", default="1", help="comma-separated seeds, e.g. 1,2,3")
    args = ap.parse_args()

    grid = GRIDS[args.grid]
    keys = list(grid)
    seeds = [int(s) for s in args.seeds.split(",")]
    scene_names = sorted(p.stem for p in SCENES.glob("*.json"))
    if args.grid in PAIRED_GRIDS:
        combos = [dict(zip(keys, vals, strict=True)) for vals in zip(*grid.values(), strict=True)]
    else:
        combos = [dict(zip(keys, v, strict=True)) for v in itertools.product(*grid.values())]
    out = str(args.out)
    jobs = [(c, s, seed, out) for seed in seeds for c in combos for s in scene_names]

    with Pool(args.workers) as pool:
        pool.map(_run_baseline, [(s, seed, out) for seed in seeds for s in scene_names])
    with Pool(args.workers, initializer=_init_worker, initargs=(args.data_dir,)) as pool:
        rows = pool.map(_run_brain, jobs, chunksize=1)

    rows.sort(key=lambda r: ([r[k] for k in keys], r["seed"], r["scene"]))
    with open(args.out / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (args.out / "results.md").write_text(summarize(rows, keys))
    print(summarize(rows, keys))


if __name__ == "__main__":
    main()
