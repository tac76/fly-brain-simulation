"""Brain-body closed loop: alternate 20 ms of brain and 20 ms of physics, one frame per interval."""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

import flybrain
from flybrain.body import BodyState, FlyBody
from flybrain.brain import LIFBrain
from flybrain.config import Config
from flybrain.connectome import Connectome
from flybrain.motor import DNRates, MotorMapper
from flybrain.recording import RecordingWriter
from flybrain.scene import Scene
from flybrain.stimulus import LoomingEncoder, threat_position

INTERVAL_S = 0.02
STEPS_PER_INTERVAL = 200  # 0.1 ms brain and physics timestep


class Controller(Protocol):
    def drive(self, t_s: float, body: BodyState) -> tuple[np.ndarray, np.ndarray, dict]:
        """Returns (drive [left, right], indices of neurons that spiked, signals for this frame)."""
        ...


class ConstantController:
    """Fixed drive, no brain. Used for replay tests and the viewer before calibration."""

    def __init__(self, drive: tuple[float, float]):
        self._drive = np.asarray(drive, dtype=float)

    def drive(self, t_s: float, body: BodyState) -> tuple[np.ndarray, np.ndarray, dict]:
        signals = {"drive_left": self._drive[0], "drive_right": self._drive[1]}
        return self._drive, np.zeros(0, dtype=np.int64), signals


class BrainController:
    """Looming input -> whole-brain model -> descending neurons -> walking drives."""

    def __init__(
        self,
        brain: LIFBrain,
        encoder: LoomingEncoder,
        mapper: MotorMapper,
        connectome: Connectome,
    ):
        self.brain, self.encoder, self.mapper = brain, encoder, mapper
        c = connectome
        self.inputs = {
            side: np.concatenate([c.indices("LPLC2", side), c.indices("LC4", side)])
            for side in ("left", "right")
        }
        self.dna = {
            side: np.concatenate([c.indices("DNa01", side), c.indices("DNa02", side)])
            for side in ("left", "right")
        }
        self.gf = np.concatenate([c.indices("DNp01", "left"), c.indices("DNp01", "right")])

    def drive(self, t_s: float, body: BodyState) -> tuple[np.ndarray, np.ndarray, dict]:
        rate_l, rate_r = self.encoder.rates(
            t_s, body.eye_left, body.eye_right, body.head, body.forward
        )
        rates = {int(i): rate_l for i in self.inputs["left"]} if rate_l > 0 else {}
        if rate_r > 0:
            rates.update({int(i): rate_r for i in self.inputs["right"]})
        counts = self.brain.step(STEPS_PER_INTERVAL, rates)
        spiking = self.brain.last_spiking()

        hz = counts / INTERVAL_S
        dn = DNRates(
            dna_left=float(hz[self.dna["left"]].sum()),
            dna_right=float(hz[self.dna["right"]].sum()),
            gf=float(hz[self.gf].mean()),
        )
        drive = self.mapper.update(dn)
        pos = threat_position(self.encoder.threat, t_s)
        signals = {
            "threat_x": pos[0],
            "threat_y": pos[1],
            "threat_z": pos[2],
            "theta_left_deg": self.encoder.last_theta_deg[0],
            "theta_right_deg": self.encoder.last_theta_deg[1],
            "input_left_hz": rate_l,
            "input_right_hz": rate_r,
            "dna_left_hz": dn.dna_left,
            "dna_right_hz": dn.dna_right,
            "gf_hz": dn.gf,
            "drive_left": drive[0],
            "drive_right": drive[1],
            "active_neurons": len(spiking),
        }
        return drive, spiking, signals


def make_brain_controller(
    scene: Scene, config: Config, connectome: Connectome, device: str = "cpu"
) -> BrainController:
    return BrainController(
        LIFBrain(connectome, device=device, seed=scene.seed),
        LoomingEncoder(config.stimulus, scene.shadow, INTERVAL_S),
        MotorMapper(config.motor, INTERVAL_S * 1000),
        connectome,
    )


@dataclass
class RunResult:
    status: str
    reason: str | None
    n_frames: int
    wall_s: float
    warnings: list[str] = field(default_factory=list)


def run_scene(
    scene: Scene,
    config: Config,
    controller: Controller,
    out_dir: Path,
    progress: Callable[[float], None] | None = None,
) -> RunResult:
    scene.validate_against(config)
    t0 = time.time()
    body = FlyBody(scene.fly, scene.seed)
    meta = {
        "scene": scene.model_dump(mode="json"),
        "seed": scene.seed,
        "config_hash": config.hash(),
        "package_version": flybrain.__version__,
    }
    writer = RecordingWriter(out_dir, meta, body.part_names)
    n_frames = math.floor(round(scene.duration_s / INTERVAL_S, 9))
    warnings: list[str] = []
    status, reason, done = "complete", None, 0

    state = body.state()
    for k in range(n_frames):
        drive, spiking, signals = controller.drive(k * INTERVAL_S, state)
        state = body.step(drive, STEPS_PER_INTERVAL)
        writer.append(body.part_poses(), spiking, signals)
        done = k + 1
        if signals.get("active_neurons", 0) > config.run.runaway_active_neurons:
            if "brain_runaway" not in warnings:
                warnings.append("brain_runaway")
        if progress:
            progress(done / n_frames)
        if state.flipped:
            status, reason = "aborted", "flipped"
        elif not state.finite:
            status, reason = "aborted", "non_finite"
        elif math.hypot(state.thorax[0], state.thorax[1]) > config.run.arena_radius_mm:
            status, reason = "aborted", "out_of_arena"
        if status == "aborted":
            break

    writer.close(status, reason=reason, warnings=warnings)
    return RunResult(status, reason, done, time.time() - t0, warnings)
