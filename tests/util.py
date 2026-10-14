import copy
import json
from pathlib import Path

EXAMPLE_SCENE = json.loads(Path("scenes/examples/loom_left.json").read_text())


def deep_merge(base: dict, patch: dict) -> dict:
    """Return a copy of base with patch merged in recursively (lists are replaced)."""
    out = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out
