import sys
from pathlib import Path

import pytest

trimesh = pytest.importorskip("trimesh")
sys.path.insert(0, str(Path("scripts")))

from export_meshes import compiled_face_count, export_fly_glb  # noqa: E402

from flybrain.body import FlyBody  # noqa: E402
from flybrain.scene import FlyStart  # noqa: E402


@pytest.mark.slow
def test_export_fly_glb(tmp_path):
    out = tmp_path / "fly.glb"
    info = export_fly_glb(out)
    names = FlyBody(FlyStart(), seed=0).part_names
    scene = trimesh.load(out, force="scene")
    node_names = [n for n in scene.graph.nodes_geometry]
    assert sorted(node_names) == sorted(names) and info["parts"] == len(names)
    assert out.stat().st_size <= 4 * 1024 * 1024
    assert info["faces"] <= 0.3 * compiled_face_count() + 200 * len(names)
