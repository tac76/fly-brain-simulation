"""Export neuron positions for the viewer's brain panel (format: docs/brain-points-format.md).

Positions are FlyWire pos_x/y/z (one representative point per neuron, voxel size 4 x 4 x 40 nm),
converted to micrometres, centred, with y and z negated (FlyWire y points ventral). Order = neuron
index of the connectome (rows of Completeness_783.csv).

    uv run python scripts/export_brain_points.py
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_OUT = Path("viewer/public/assets")
VOXEL_UM = np.array([0.004, 0.004, 0.04])
FLIP = np.array([1.0, -1.0, -1.0])

SUPER_CLASSES = [
    "optic", "central", "sensory", "visual_projection", "ascending", "descending",
    "sensory_ascending", "visual_centrifugal", "motor", "endocrine",
]
HIGHLIGHT = {  # (cell_type, side) -> group
    ("LPLC2", "left"): "LPLC2_L", ("LPLC2", "right"): "LPLC2_R",
    ("LC4", "left"): "LC4_L", ("LC4", "right"): "LC4_R",
    ("DNp01", "left"): "DNp01_L", ("DNp01", "right"): "DNp01_R",
    ("DNa01", "left"): "DNa_L", ("DNa02", "left"): "DNa_L",
    ("DNa01", "right"): "DNa_R", ("DNa02", "right"): "DNa_R",
}
GROUPS = ["unknown", *SUPER_CLASSES, *dict.fromkeys(HIGHLIGHT.values())]
COLORS = {
    "unknown": "#3a3f4b", "optic": "#2f5d8a", "central": "#4a6fa5", "sensory": "#3d8a7a",
    "visual_projection": "#5a7fc0", "ascending": "#6b5b95", "descending": "#8a6bb0",
    "sensory_ascending": "#3d7a8a", "visual_centrifugal": "#4a5d8a", "motor": "#9a6b8a",
    "endocrine": "#7a7a5a",
    "LPLC2_L": "#4fd1ff", "LPLC2_R": "#4fd1ff", "LC4_L": "#7fffd4", "LC4_R": "#7fffd4",
    "DNp01_L": "#ffd700", "DNp01_R": "#ffd700", "DNa_L": "#ff6b9d", "DNa_R": "#ff6b9d",
}


def export_brain_points(data_dir: Path, out_dir: Path) -> dict:
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    root_ids = pd.read_csv(data_dir / "Completeness_783.csv", index_col=0).index
    ann = pd.read_csv(
        data_dir / "neuron_annotations.tsv",
        sep="\t",
        usecols=["root_id", "pos_x", "pos_y", "pos_z", "super_class", "cell_type", "side"],
        low_memory=False,
    ).drop_duplicates("root_id").set_index("root_id").reindex(root_ids)

    raw = ann[["pos_x", "pos_y", "pos_z"]].to_numpy(dtype=float)
    known = ~np.isnan(raw).any(axis=1)
    pos = raw * VOXEL_UM * FLIP
    center = pos[known].mean(axis=0)
    pos = np.where(known[:, None], pos - center, 0.0).astype("<f4")

    group = np.zeros(len(root_ids), dtype=np.uint8)
    sc = ann["super_class"].fillna("").to_numpy()
    for name in SUPER_CLASSES:
        group[sc == name] = GROUPS.index(name)
    ct, side = ann["cell_type"].fillna("").to_numpy(), ann["side"].fillna("").to_numpy()
    for (t, s), name in HIGHLIGHT.items():
        group[(ct == t) & (side == s)] = GROUPS.index(name)
    group[~known] = 0

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "brain_points.bin").write_bytes(pos.tobytes() + group.tobytes())
    meta = {
        "n": len(root_ids),
        "groups": GROUPS,
        "colors": COLORS,
        "highlight": list(dict.fromkeys(HIGHLIGHT.values())),
        "bounds_um": [pos.min(axis=0).round(2).tolist(), pos.max(axis=0).round(2).tolist()],
        "license": "Derived from FlyWire FAFB v783 (CC BY-NC 4.0)",
    }
    (out_dir / "brain_points.json").write_text(json.dumps(meta, indent=1) + "\n")
    return {"n": meta["n"], "bytes": (out_dir / "brain_points.bin").stat().st_size}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    print(export_brain_points(args.data_dir, args.out))
