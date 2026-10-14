"""FlyWire v783 connectome: download, checksum, and a compact pre-major CSR representation.

Data sources (pinned commits, CC BY-NC 4.0, see DATA_LICENSE.md):
- Shiu et al. 2024 model repository: neuron list and signed connectivity.
- Schlegel et al. 2024 FlyWire annotations: cell types and soma side.
"""

import hashlib
import shutil
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

_GH = "https://raw.githubusercontent.com"
_SHIU = f"{_GH}/philshiu/Drosophila_brain_model/91bdd1e7dcf193f3e7ca5a8933497fcef63b7960"
_ANN = f"{_GH}/flyconnectome/flywire_annotations/a83b2776d60d5764cef36b927f5f9679c16c47a2"

DATA_FILES: dict[str, tuple[str, str]] = {
    "Completeness_783.csv": (
        f"{_SHIU}/Completeness_783.csv",
        "bbb847a4cc2caaa7a16349722d220c087317b946d148d4d592d94d250617a311",
    ),
    "Connectivity_783.parquet": (
        f"{_SHIU}/Connectivity_783.parquet",
        "efeb23fb99098e9c390f6869969b2a121a2ee92c833cfc45ecb2c1d8e1af0347",
    ),
    "neuron_annotations.tsv": (
        f"{_ANN}/supplemental_files/Supplemental_file1_neuron_annotations.tsv",
        "b214970b55d2fbe0853bba536fdcb9e28730f4eb7ab06f600491df795da683cd",
    ),
}

_HINT = "run `flybrain download-data`"


class DataError(Exception):
    """Connectome data missing or corrupted."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_data(data_dir: Path) -> None:
    """Download all data files into data_dir, skipping files that already verify."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, (url, sha) in DATA_FILES.items():
        target = data_dir / name
        if target.exists() and _sha256(target) == sha:
            continue
        tmp = target.with_suffix(target.suffix + ".part")
        with urllib.request.urlopen(url) as resp, open(tmp, "wb") as out:
            shutil.copyfileobj(resp, out, length=1 << 20)
        if _sha256(tmp) != sha:
            tmp.unlink()
            raise DataError(f"{name}: checksum mismatch after download from {url}")
        tmp.replace(target)


def _verified(data_dir: Path, name: str) -> Path:
    path = Path(data_dir) / name
    if not path.exists():
        raise DataError(f"{name} not found in {data_dir}; {_HINT}")
    if _sha256(path) != DATA_FILES[name][1]:
        raise DataError(f"{name} in {data_dir} fails its checksum; {_HINT}")
    return path


@dataclass(frozen=True)
class Connectome:
    n: int
    root_ids: np.ndarray  # int64, FlyWire root id per neuron index
    pre_indptr: np.ndarray  # int64, len n+1; edges of neuron i: [indptr[i], indptr[i+1])
    post_idx: np.ndarray  # int32, postsynaptic neuron index per edge
    weight_syn: np.ndarray  # float32, signed synapse count per edge
    cell_type: np.ndarray  # object (str), "" if unannotated
    side: np.ndarray  # object (str), "left"/"right"/"center"/""

    @classmethod
    def from_edges(
        cls,
        n: int,
        pre: Sequence[int],
        post: Sequence[int],
        weight: Sequence[float],
        cell_type: Sequence[str] | None = None,
        side: Sequence[str] | None = None,
        root_ids: Sequence[int] | None = None,
    ) -> "Connectome":
        pre = np.asarray(pre, dtype=np.int64)
        order = np.argsort(pre, kind="stable")
        counts = np.bincount(pre, minlength=n)
        indptr = np.zeros(n + 1, dtype=np.int64)
        np.cumsum(counts, out=indptr[1:])
        return cls(
            n=n,
            root_ids=np.asarray(root_ids if root_ids is not None else np.arange(n), dtype=np.int64),
            pre_indptr=indptr,
            post_idx=np.asarray(post, dtype=np.int32)[order],
            weight_syn=np.asarray(weight, dtype=np.float32)[order],
            cell_type=np.asarray(cell_type if cell_type is not None else [""] * n, dtype=object),
            side=np.asarray(side if side is not None else [""] * n, dtype=object),
        )

    @classmethod
    def from_files(cls, data_dir: Path) -> "Connectome":
        comp_path = _verified(data_dir, "Completeness_783.csv")
        con_path = _verified(data_dir, "Connectivity_783.parquet")
        ann_path = _verified(data_dir, "neuron_annotations.tsv")

        root_ids = pd.read_csv(comp_path, index_col=0).index.to_numpy(dtype=np.int64)
        con = pd.read_parquet(
            con_path,
            columns=["Presynaptic_Index", "Postsynaptic_Index", "Excitatory x Connectivity"],
        )
        ann = pd.read_csv(
            ann_path, sep="\t", usecols=["root_id", "cell_type", "side"], low_memory=False
        ).drop_duplicates("root_id")
        ann = ann.set_index("root_id").reindex(root_ids)
        return cls.from_edges(
            len(root_ids),
            con["Presynaptic_Index"].to_numpy(),
            con["Postsynaptic_Index"].to_numpy(),
            con["Excitatory x Connectivity"].to_numpy(),
            cell_type=ann["cell_type"].fillna("").to_numpy(dtype=object),
            side=ann["side"].fillna("").to_numpy(dtype=object),
            root_ids=root_ids,
        )

    def indices(self, cell_type: str, side: str | None = None) -> np.ndarray:
        mask = self.cell_type == cell_type
        if side is not None:
            mask &= self.side == side
        idx = np.flatnonzero(mask).astype(np.int64)
        if len(idx) == 0:
            where = f" on side {side!r}" if side else ""
            raise KeyError(f"no neurons of type {cell_type!r}{where}")
        return idx
