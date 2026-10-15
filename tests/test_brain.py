from pathlib import Path

import numpy as np
import pytest

from flybrain.brain import LIFBrain
from flybrain.connectome import Connectome


def test_silent_without_input(tiny_connectome):
    b = LIFBrain(tiny_connectome)
    assert b.step(2000, {}).sum() == 0


def test_excitatory_chain_propagates(tiny_connectome):
    b = LIFBrain(tiny_connectome, seed=1)
    c = b.step(5000, {0: 100.0})  # 0.5 s at 100 Hz
    assert c[0] > 20 and c[1] > 0 and c[2] > 0 and c[5] == 0


def test_inhibitory_input_does_not_cause_spikes(tiny_connectome):
    c = LIFBrain(tiny_connectome).step(5000, {3: 100.0})
    assert c[3] > 20 and c[4] == 0


def test_synaptic_delay(tiny_connectome):
    # first spike of neuron 1 occurs >= 18 steps (1.8 ms) after first spike of neuron 0
    b = LIFBrain(tiny_connectome, seed=2)
    first = {0: None, 1: None}
    for k in range(3000):
        b.step(1, {0: 200.0})
        spiking = set(b.last_spiking().tolist())
        for i in first:
            if first[i] is None and i in spiking:
                first[i] = k
    assert first[0] is not None and first[1] is not None
    assert first[1] - first[0] >= 18


def test_deterministic_on_cpu(tiny_connectome):
    a = LIFBrain(tiny_connectome, seed=7).step(3000, {0: 80.0})
    b = LIFBrain(tiny_connectome, seed=7).step(3000, {0: 80.0})
    assert np.array_equal(a, b)


def test_reset_restores_rest_and_reseeds(tiny_connectome):
    b = LIFBrain(tiny_connectome, seed=3)
    first = b.step(3000, {0: 80.0})
    b.reset(seed=3)
    assert np.array_equal(b.step(3000, {0: 80.0}), first)


@pytest.mark.slow
def test_real_brain_looming_matches_spike():
    c = Connectome.from_files(Path("data"))
    b = LIFBrain(c, seed=0)
    inp = {int(i): 150.0 for t in ("LPLC2", "LC4") for i in c.indices(t, "left")}
    counts = b.step(5000, inp)  # 0.5 s
    assert 670 <= (counts > 0).sum() <= 910  # Brian2 reference: 790 (+-15 %)
    (gf_l,) = c.indices("DNp01", "left")
    assert counts[gf_l] / 0.5 > 100  # giant fiber strongly active
    dna_r = sum(counts[c.indices(t, "right")].sum() for t in ("DNa01", "DNa02"))
    dna_l = sum(counts[c.indices(t, "left")].sum() for t in ("DNa01", "DNa02"))
    assert dna_r > dna_l  # contralateral steering bias
