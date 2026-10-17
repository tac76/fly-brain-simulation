"""Run every gallery scene and write the recordings plus index.json for the viewer.

scenes/gallery/<id>.json is the scene, <id>.gallery.json holds title, description, order and an
optional "no_brain": true.

    uv run python scripts/build_gallery.py
"""

import argparse
import json
import shutil
from pathlib import Path

from flybrain.config import load_config
from flybrain.connectome import Connectome
from flybrain.loop import ConstantController, make_brain_controller, run_scene
from flybrain.scene import load_scene


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", type=Path, default=Path("scenes/gallery"))
    ap.add_argument("--out", type=Path, default=Path("viewer/public/gallery"))
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--only", nargs="*", help="rebuild only these ids (index is always rewritten)")
    args = ap.parse_args()

    cfg = load_config()
    connectome = None
    entries = []
    for scene_file in sorted(args.scenes.glob("*.json")):
        if scene_file.name.endswith(".gallery.json"):
            continue
        gid = scene_file.stem
        info = json.loads(scene_file.with_suffix(".gallery.json").read_text())
        no_brain = bool(info.get("no_brain", False))
        entries.append({
            "id": gid,
            "title": info["title"],
            "description": info["description"],
            "path": f"{gid}/",
            "brain": not no_brain,
            "order": info.get("order", 99),
        })
        if args.only and gid not in args.only:
            continue
        scene = load_scene(scene_file)
        out = args.out / gid
        if out.exists():
            shutil.rmtree(out)
        if no_brain:
            ctrl = ConstantController((cfg.motor.base_drive, cfg.motor.base_drive))
        else:
            connectome = connectome or Connectome.from_files(args.data_dir)
            ctrl = make_brain_controller(scene, cfg, connectome)
        result = run_scene(scene, cfg, ctrl, out)
        print(f"{gid}: {result.status}, {result.n_frames} frames, {result.wall_s:.0f} s")

    entries.sort(key=lambda e: (e.pop("order"), e["id"]))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "index.json").write_text(json.dumps(entries, indent=1) + "\n")


if __name__ == "__main__":
    main()
