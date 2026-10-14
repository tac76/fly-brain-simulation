"""Physically simulated fly body: FlyGym 1.2.x NeuroMechFly with its HybridTurningController.

The leg movements come from the controller (coupled oscillators, a recorded real step cycle and
reflex rules); physics (joint actuators, contacts, friction, adhesion) is computed by MuJoCo.
The only inputs are the two drives [left, right]; the side with the smaller drive turns inward.
"""

import math
import warnings
from dataclasses import dataclass

import mujoco
import numpy as np
from flygym import Fly
from flygym.arena import FlatTerrain
from flygym.examples.locomotion import HybridTurningController

from flybrain.scene import FlyStart

_LEGS = ["LF", "LM", "LH", "RF", "RM", "RH"]
_SEGMENTS = ["Tibia", "Tarsus1", "Tarsus2", "Tarsus3", "Tarsus4", "Tarsus5"]


@dataclass
class BodyState:
    thorax: np.ndarray
    head: np.ndarray
    eye_left: np.ndarray
    eye_right: np.ndarray
    forward: np.ndarray  # unit vector in the ground plane (z = 0)
    flipped: bool
    finite: bool


class FlyBody:
    def __init__(self, start: FlyStart, seed: int):
        x, y = start.pos
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.fly = Fly(
                spawn_pos=(x, y, 0.2),
                spawn_orientation=(0, 0, math.radians(start.heading_deg)),
                enable_adhesion=True,
                contact_sensor_placements=[f"{leg}{seg}" for leg in _LEGS for seg in _SEGMENTS],
            )
            self.sim = HybridTurningController(
                fly=self.fly, cameras=[], arena=FlatTerrain(), timestep=1e-4, seed=seed
            )
            self.sim.reset(seed=seed)
        physics = self.sim.physics
        model = self.fly.model
        self._thorax = physics.bind(model.find("body", "Thorax"))
        self._head = physics.bind(model.find("body", "Head"))
        self._eyes = physics.bind([model.find("body", "LEye"), model.find("body", "REye")])
        mesh_geoms = [g for g in model.find_all("geom") if g.mesh is not None]
        self.part_names: list[str] = [g.name for g in mesh_geoms]
        self._geoms = physics.bind(mesh_geoms)
        self._flipped = False

    def step(self, drive: np.ndarray, n_steps: int) -> BodyState:
        action = np.asarray(drive, dtype=float)
        for _ in range(n_steps):
            _, _, terminated, _, info = self.sim.step(action)
            if terminated or info.get("flip", False):
                self._flipped = True
                break
        return self.state()

    def state(self) -> BodyState:
        xmat = np.asarray(self._thorax.xmat).reshape(3, 3)
        fwd = np.array([xmat[0, 0], xmat[1, 0], 0.0])
        norm = np.linalg.norm(fwd)
        fwd = fwd / norm if norm > 0 else np.array([1.0, 0.0, 0.0])
        thorax = np.array(self._thorax.xpos, dtype=float)
        head = np.array(self._head.xpos, dtype=float)
        eyes = np.array(self._eyes.xpos, dtype=float)
        finite = bool(np.isfinite(thorax).all() and np.isfinite(self._geoms.xpos).all())
        return BodyState(thorax, head, eyes[0], eyes[1], fwd, self._flipped, finite)

    def part_poses(self) -> np.ndarray:
        """World pose of every mesh geom: (69, 7) float32, position + quaternion (w, x, y, z)."""
        pos = np.asarray(self._geoms.xpos)
        mats = np.asarray(self._geoms.xmat)
        out = np.empty((len(pos), 7), dtype=np.float32)
        quat = np.empty(4)
        for i, m in enumerate(mats):
            mujoco.mju_mat2Quat(quat, np.ascontiguousarray(m, dtype=np.float64))
            out[i, :3] = pos[i]
            out[i, 3:] = quat
        return out
