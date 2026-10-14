"""Calibration constants and run limits, loaded from a versioned YAML file."""

import hashlib
import json
from pathlib import Path

import yaml
from pydantic import BaseModel

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default.yaml"


class StimulusConfig(BaseModel):
    r_max_hz: float = 150
    theta_min_deg: float = 5
    theta_dot_0_deg_s: float = 20
    theta_dot_sat_deg_s: float = 300
    overlap_deg: float = 20


class MotorConfig(BaseModel):
    base_drive: float = 0.7
    tau_ms: float = 50
    k_turn: float = 0.01
    k_gf: float = 0.01
    boost_max: float = 0.8
    drive_min: float = 0.0
    drive_max: float = 1.5


class RunConfig(BaseModel):
    arena_radius_mm: float = 60
    runaway_active_neurons: int = 5000


class Config(BaseModel):
    stimulus: StimulusConfig = StimulusConfig()
    motor: MotorConfig = MotorConfig()
    run: RunConfig = RunConfig()

    def hash(self) -> str:
        """Short, stable fingerprint of all values (first 12 hex chars of sha256)."""
        canonical = json.dumps(self.model_dump(), sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def load_config(path: Path | None = None) -> Config:
    data = yaml.safe_load(Path(path or DEFAULT_CONFIG_PATH).read_text()) or {}
    return Config.model_validate(data)
