"""Scene description: what the user sets up before pressing Apply."""

import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, FiniteFloat, field_validator

from flybrain.config import Config

Point3 = tuple[FiniteFloat, FiniteFloat, FiniteFloat]


class FlyStart(BaseModel):
    pos: tuple[FiniteFloat, FiniteFloat] = (0.0, 0.0)
    heading_deg: FiniteFloat = 0.0


class Threat(BaseModel):
    size_mm: float = Field(gt=0, allow_inf_nan=False, description="diameter of the threat")
    speed_mm_s: float = Field(gt=0, allow_inf_nan=False)
    path: list[Point3] = Field(min_length=2, max_length=4)

    @field_validator("path")
    @classmethod
    def _check_path(cls, path: list[Point3]) -> list[Point3]:
        for p in path:
            if p[2] < 0:
                raise ValueError("path point below the ground (z < 0)")
        for a, b in zip(path, path[1:], strict=False):
            if math.dist(a, b) == 0:
                raise ValueError("path has duplicate consecutive points")
        return path


class Scene(BaseModel):
    duration_s: float = Field(ge=0.02, le=10, description="at least one 20 ms frame")
    seed: int = Field(ge=0, le=2**32 - 1)
    fly: FlyStart = FlyStart()
    shadow: Threat
    environment: Literal["tabletop"] = "tabletop"

    def validate_against(self, config: Config) -> None:
        """Checks that depend on the run configuration."""
        if math.hypot(*self.fly.pos) > config.run.arena_radius_mm:
            raise ValueError(
                f"fly start {self.fly.pos} is outside the arena "
                f"(radius {config.run.arena_radius_mm} mm)"
            )


def load_scene(path: Path) -> Scene:
    return Scene.model_validate_json(Path(path).read_text())
