"""Export the NeuroMechFly meshes (as compiled by MuJoCo) to a GLB for the browser viewer.

One node per mesh geom, named like FlyBody.part_names, vertices in the geom frame (mm), so the
viewer can place each node directly with the poses from body.bin.

    uv run --group assets python scripts/export_meshes.py
"""

import argparse
from pathlib import Path

import fast_simplification
import numpy as np
import trimesh

from flybrain.body import FlyBody
from flybrain.scene import FlyStart

DEFAULT_OUT = Path("viewer/public/assets/fly.glb")
MIN_FACES = 200

# RGBA per part-name pattern (first match wins)
COLORS = [
    ("Eye", (120, 20, 20, 255)),
    ("Wing", (200, 210, 220, 90)),
    ("Haltere", (170, 150, 110, 255)),
    ("Arista", (90, 70, 40, 255)),
    ("Tarsus", (90, 60, 30, 255)),
    ("", (150, 100, 45, 255)),
]


def _compiled_meshes():
    body = FlyBody(FlyStart(), seed=0)
    model = body.sim.physics.model
    geoms = [g for g in body.fly.model.find_all("geom") if g.mesh is not None]
    bound = body.sim.physics.bind(geoms)
    out = []
    for name, mesh_id in zip(body.part_names, np.asarray(bound.dataid), strict=True):
        va, vn = model.mesh_vertadr[mesh_id], model.mesh_vertnum[mesh_id]
        fa, fn = model.mesh_faceadr[mesh_id], model.mesh_facenum[mesh_id]
        verts = np.array(model.mesh_vert[va : va + vn], dtype=np.float32)
        faces = np.array(model.mesh_face[fa : fa + fn], dtype=np.int64)
        out.append((name, verts, faces))
    return out


def compiled_face_count() -> int:
    return sum(len(f) for _, _, f in _compiled_meshes())


def _color(name: str) -> tuple[int, int, int, int]:
    return next(c for pattern, c in COLORS if pattern in name)


def export_fly_glb(out: Path = DEFAULT_OUT, target_ratio: float = 0.3) -> dict:
    scene = trimesh.Scene()
    total = 0
    for name, verts, faces in _compiled_meshes():
        if len(faces) > MIN_FACES:
            keep = max(target_ratio, MIN_FACES / len(faces))
            verts, faces = fast_simplification.simplify(verts, faces, target_reduction=1 - keep)
        mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
        rgba = _color(name)
        mesh.visual = trimesh.visual.ColorVisuals(mesh, face_colors=np.tile(rgba, (len(faces), 1)))
        scene.add_geometry(mesh, node_name=name, geom_name=name)
        total += len(faces)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    scene.export(out)
    return {"parts": len(scene.graph.nodes_geometry), "faces": total, "bytes": out.stat().st_size}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--ratio", type=float, default=0.3)
    args = ap.parse_args()
    print(export_fly_glb(args.out, args.ratio))
