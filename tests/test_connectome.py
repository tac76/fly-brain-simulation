from pathlib import Path

import pytest

from flybrain.connectome import DATA_FILES, Connectome, DataError


def test_from_edges_builds_pre_major_csr(tiny_connectome):
    c = tiny_connectome
    assert c.n == 6 and c.pre_indptr[0] == 0 and c.pre_indptr[-1] == len(c.post_idx)
    s, e = c.pre_indptr[0], c.pre_indptr[1]
    assert list(c.post_idx[s:e]) == [1]
    s, e = c.pre_indptr[3], c.pre_indptr[4]
    assert list(c.weight_syn[s:e]) == [-250.0]


def test_indices_by_type(tiny_connectome):
    assert list(tiny_connectome.indices("OUT")) == [2]
    with pytest.raises(KeyError):
        tiny_connectome.indices("NOPE")


def test_missing_file_raises_data_error(tmp_path):
    with pytest.raises(DataError, match="Completeness_783.csv.*download-data"):
        Connectome.from_files(tmp_path)


def test_corrupt_file_raises_data_error(tmp_path):
    for name in DATA_FILES:
        (tmp_path / name).write_text("x")
    with pytest.raises(DataError, match="checksum"):
        Connectome.from_files(tmp_path)


@pytest.mark.slow
def test_real_connectome():
    c = Connectome.from_files(Path("data"))
    assert c.n == 138639 and len(c.post_idx) == 15091983
    assert len(c.indices("LPLC2", "left")) > 90 and len(c.indices("DNp01", "left")) == 1
