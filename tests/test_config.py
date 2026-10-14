from flybrain.config import load_config


def test_default_config_loads_and_hash_is_stable():
    a, b = load_config(), load_config()
    assert a.stimulus.r_max_hz == 150 and a.hash() == b.hash() and len(a.hash()) == 12
