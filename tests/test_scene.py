from pathlib import Path

import pytest
from pydantic import ValidationError
from util import EXAMPLE_SCENE, deep_merge

from flybrain.config import load_config
from flybrain.scene import Scene, load_scene


def test_example_scene_loads():
    s = load_scene(Path("scenes/examples/loom_left.json"))
    assert s.duration_s == 3 and len(s.shadow.path) == 2


@pytest.mark.parametrize(
    "patch,field",
    [
        ({"duration_s": 0}, "duration_s"),
        ({"duration_s": 10.5}, "duration_s"),
        ({"shadow": {"path": [[0, 0, 5]]}}, "path"),
        ({"shadow": {"path": [[0, 0, 5]] * 5}}, "path"),
        ({"shadow": {"path": [[10, 0, -1], [0, 0, 3]]}}, "path"),
        ({"shadow": {"path": [[10, 0, 3], [10, 0, 3]]}}, "path"),
        ({"shadow": {"size_mm": 0}}, "size_mm"),
        ({"environment": "space"}, "environment"),
    ],
)
def test_invalid_scene_rejected(patch, field):
    with pytest.raises(ValidationError) as e:
        Scene.model_validate(deep_merge(EXAMPLE_SCENE, patch))
    assert field in str(e.value)


def test_fly_outside_arena_rejected():
    s = Scene.model_validate(deep_merge(EXAMPLE_SCENE, {"fly": {"pos": [100, 0]}}))
    with pytest.raises(ValueError, match="arena"):
        s.validate_against(load_config())
