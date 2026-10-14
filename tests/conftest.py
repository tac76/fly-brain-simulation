import numpy as np
import pytest

from flybrain.connectome import Connectome

STRONG = 250.0  # synapses: g jump 68.75 mV peaks v at ~+10.8 mV > 7 mV threshold gap


@pytest.fixture
def tiny_connectome() -> Connectome:
    """6 neurons: 0->1->2 excitatory chain, 3-|4 inhibitory, 5 isolated."""
    pre = np.array([0, 1, 3])
    post = np.array([1, 2, 4])
    weight = np.array([STRONG, STRONG, -STRONG])
    return Connectome.from_edges(
        6, pre, post, weight, cell_type=["IN_L", "MID", "OUT", "IN_R", "OUTR", "ISO"]
    )


@pytest.fixture
def fixture_connectome() -> Connectome:
    """Looming pathway in miniature: each eye's LPLC2/LC4 drive the same-side giant fiber and the
    opposite-side steering neurons (as in the real connectome)."""
    names = []
    for side in ("left", "right"):
        for t in ("LPLC2", "LPLC2", "LC4", "LC4", "DNa01", "DNa02", "DNp01"):
            names.append((t, side))
    idx = {}
    for i, key in enumerate(names):
        idx.setdefault(key, []).append(i)
    pre, post, w = [], [], []
    for side, other in (("left", "right"), ("right", "left")):
        for t in ("LPLC2", "LC4"):
            for src in idx[(t, side)]:
                for dst in idx[("DNp01", side)] + idx[("DNa01", other)] + idx[("DNa02", other)]:
                    pre.append(src)
                    post.append(dst)
                    w.append(STRONG)
    return Connectome.from_edges(
        len(names), pre, post, w, cell_type=[n[0] for n in names], side=[n[1] for n in names]
    )
