"""Leaky integrate-and-fire model of the whole fly brain (Shiu et al. 2024), event-driven.

Equations and parameters follow github.com/philshiu/Drosophila_brain_model (model.py):

    dv/dt = (v_0 - v + g) / t_mbr      (frozen while refractory)
    dg/dt = -g / tau                   (frozen while refractory)
    spike when v > v_th: v = v_rst, g = 0, refractory for t_rfc
    a presynaptic spike adds w_syn * (signed synapse count) to g after t_dly

External input is Poisson: each event adds f_poi * w_syn to v (enough to cause a spike).
Input neurons have no refractory period, as in the original model.
"""

import math
from dataclasses import dataclass

import numpy as np
import torch

from flybrain.connectome import Connectome


@dataclass
class BrainParams:
    dt_ms: float = 0.1
    v_0: float = -52.0  # mV
    v_rst: float = -52.0
    v_th: float = -45.0
    t_mbr_ms: float = 20.0
    tau_ms: float = 5.0
    t_rfc_ms: float = 2.2
    t_dly_ms: float = 1.8
    w_syn: float = 0.275  # mV per synapse
    f_poi: float = 250.0  # Poisson kick = f_poi * w_syn = 68.75 mV


class LIFBrain:
    def __init__(
        self,
        connectome: Connectome,
        params: BrainParams | None = None,
        device: str = "cpu",
        seed: int = 0,
    ):
        self.c = connectome
        self.p = params or BrainParams()
        self.device = torch.device(device)
        p = self.p
        self.n = connectome.n
        self.n_dly = round(p.t_dly_ms / p.dt_ms)
        self.n_rfc = round(p.t_rfc_ms / p.dt_ms)
        self.a_v = math.exp(-p.dt_ms / p.t_mbr_ms)
        self.a_g = math.exp(-p.dt_ms / p.tau_ms)
        self.kick = p.f_poi * p.w_syn

        dev = self.device
        self.indptr = torch.as_tensor(connectome.pre_indptr, dtype=torch.int64, device=dev)
        self.post = torch.as_tensor(connectome.post_idx, dtype=torch.int64, device=dev)
        self.w = torch.as_tensor(connectome.weight_syn * p.w_syn, dtype=torch.float32, device=dev)
        self.reset(seed)

    def reset(self, seed: int) -> None:
        """Return to rest, clear pending synaptic input, reseed the Poisson generator."""
        dev = self.device
        self.v = torch.full((self.n,), self.p.v_0, dtype=torch.float32, device=dev)
        self.g = torch.zeros(self.n, dtype=torch.float32, device=dev)
        self.rfc = torch.zeros(self.n, dtype=torch.int32, device=dev)
        self.buf = torch.zeros((self.n_dly, self.n), dtype=torch.float32, device=dev)
        self.k = 0
        self.gen = torch.Generator(device="cpu").manual_seed(seed)
        self._last = torch.zeros(self.n, dtype=torch.bool, device=dev)

    def step(self, n_steps: int, input_rates: dict[int, float]) -> np.ndarray:
        """Advance n_steps of dt; returns int32 spike counts per neuron for these steps."""
        dev, p = self.device, self.p
        if input_rates:
            in_idx = torch.tensor(list(input_rates.keys()), dtype=torch.int64, device=dev)
            in_p = torch.tensor(
                [r * p.dt_ms / 1000.0 for r in input_rates.values()], dtype=torch.float32
            )
            is_input = torch.zeros(self.n, dtype=torch.bool, device=dev)
            is_input[in_idx] = True
        counts = torch.zeros(self.n, dtype=torch.int32, device=dev)
        spiked_any = torch.zeros(self.n, dtype=torch.bool, device=dev)

        for _ in range(n_steps):
            slot = self.k % self.n_dly
            self.g += self.buf[slot]
            self.buf[slot].zero_()

            active = self.rfc <= 0
            v_new = p.v_0 + (self.v - p.v_0) * self.a_v + self.g * (1.0 - self.a_v)
            self.v = torch.where(active, v_new, self.v)
            self.g = torch.where(active, self.g * self.a_g, self.g)
            self.rfc -= (~active).to(torch.int32)

            if input_rates:
                hit = torch.rand(len(in_p), generator=self.gen) < in_p
                if hit.any():
                    self.v[in_idx[hit.to(dev)]] += self.kick

            spk = torch.nonzero(self.v > p.v_th).squeeze(1)
            if len(spk):
                counts[spk] += 1
                spiked_any[spk] = True
                self.v[spk] = p.v_rst
                self.g[spk] = 0.0
                rfc = torch.full_like(spk, self.n_rfc, dtype=torch.int32)
                if input_rates:
                    rfc = torch.where(is_input[spk], 0, rfc)
                self.rfc[spk] = rfc
                self._deliver(spk, slot)
            self.k += 1

        self._last = spiked_any
        return counts.cpu().numpy()

    def _deliver(self, spk: torch.Tensor, slot: int) -> None:
        """Queue synaptic input of spiking neurons; it arrives n_dly steps later."""
        starts = self.indptr[spk]
        lens = self.indptr[spk + 1] - starts
        total = int(lens.sum())
        if total == 0:
            return
        seg_offset = torch.repeat_interleave(starts - (torch.cumsum(lens, 0) - lens), lens)
        edges = seg_offset + torch.arange(total, device=self.device)
        self.buf[slot].index_add_(0, self.post[edges], self.w[edges])

    def last_spiking(self) -> np.ndarray:
        """Indices of neurons that spiked at least once during the last step() call."""
        return torch.nonzero(self._last).squeeze(1).cpu().numpy().astype(np.int64)
