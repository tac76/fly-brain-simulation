import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path("scripts")))
from export_brain_points import export_brain_points  # noqa: E402

HEADER = "root_id\tpos_x\tpos_y\tpos_z\tsuper_class\tcell_type\tside\n"


def _fixture(tmp_path):
    (tmp_path / "Completeness_783.csv").write_text(
        "Unnamed: 0,Completed\n11,True\n12,True\n13,True\n14,True\n"
    )
    (tmp_path / "neuron_annotations.tsv").write_text(
        HEADER
        + "11\t1000\t1000\t100\tcentral\tCB0001\tleft\n"
        + "12\t2000\t2000\t200\toptic\tLPLC2\tleft\n"
        + "13\t1000\t1000\t100\tdescending\tDNa02\tright\n"
    )  # neuron 14 has no annotation
    return tmp_path


def _read(out):
    meta = json.loads((out / "brain_points.json").read_text())
    raw = (out / "brain_points.bin").read_bytes()
    n = meta["n"]
    pos = np.frombuffer(raw[: n * 12], dtype="<f4").reshape(n, 3)
    grp = np.frombuffer(raw[n * 12 :], dtype=np.uint8)
    return meta, pos, grp


def test_groups_scaling_and_centring(tmp_path):
    out = tmp_path / "out"
    export_brain_points(_fixture(tmp_path), out)
    meta, pos, grp = _read(out)
    names = [meta["groups"][g] for g in grp]
    assert names == ["central", "LPLC2_L", "DNa_R", "unknown"]
    # neuron 1 is (1000, 1000, 100) voxels from neuron 0: (4, 4, 4) um, y and z negated
    assert pos[1] - pos[0] == pytest.approx([4.0, -4.0, -4.0])
    assert pos[:3].mean(axis=0) == pytest.approx([0, 0, 0], abs=1e-5)
    assert pos[3] == pytest.approx([0, 0, 0], abs=1e-5)  # unannotated -> mean position
    assert set(meta["colors"]) == set(meta["groups"])


@pytest.mark.slow
def test_real_brain_points(tmp_path):
    info = export_brain_points(Path("data"), tmp_path)
    meta, _, grp = _read(tmp_path)
    assert meta["n"] == 138639 == info["n"]
    assert (tmp_path / "brain_points.bin").stat().st_size <= 2.5 * 1024 * 1024
    assert (grp == meta["groups"].index("DNp01_L")).sum() == 1
    assert (grp == meta["groups"].index("LPLC2_L")).sum() > 90
