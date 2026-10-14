import numpy as np
import pytest

from flybrain.connectome import Connectome

STRONG = 60.0  # synapses; one presynaptic spike reliably drives the target (0.275 mV each)


@pytest.fixture
def tiny_connectome() -> Connectome:
    """6 neurons: 0->1->2 excitatory chain, 3-|4 inhibitory, 5 isolated."""
    pre = np.array([0, 1, 3])
    post = np.array([1, 2, 4])
    weight = np.array([STRONG, STRONG, -STRONG])
    return Connectome.from_edges(
        6, pre, post, weight, cell_type=["IN_L", "MID", "OUT", "IN_R", "OUTR", "ISO"]
    )
