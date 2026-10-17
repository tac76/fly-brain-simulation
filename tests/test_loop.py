import pytest
from util import EXAMPLE_SCENE, deep_merge

from flybrain.config import load_config
from flybrain.loop import ConstantController, make_brain_controller, run_scene
from flybrain.recording import read_recording
from flybrain.scene import Scene


def scene_with(**patch) -> Scene:
    return Scene.model_validate(deep_merge(EXAMPLE_SCENE, patch))


SHORT = scene_with(duration_s=0.2)
# fast threat diving at the fly from its left
LOUD = scene_with(
    duration_s=0.2, shadow={"size_mm": 8, "speed_mm_s": 300, "path": [[0, 15, 2], [0, 1, 2]]}
)


def test_frame_count_floors_duration(tmp_path):
    r = run_scene(scene_with(duration_s=0.21), load_config(), ConstantController((1, 1)), tmp_path)
    assert r.status == "complete" and r.n_frames == 10
    assert read_recording(tmp_path).meta["n_frames"] == 10


def test_deterministic_recording(tmp_path, fixture_connectome):
    for d in ("a", "b"):
        ctrl = make_brain_controller(LOUD, load_config(), fixture_connectome)
        run_scene(LOUD, load_config(), ctrl, tmp_path / d)
    for f in ("meta.json", "body.bin", "spikes.bin", "signals.json"):
        assert (tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes()


def test_brain_run_records_signals_and_spikes(tmp_path, fixture_connectome):
    ctrl = make_brain_controller(LOUD, load_config(), fixture_connectome)
    run_scene(LOUD, load_config(), ctrl, tmp_path)
    rec = read_recording(tmp_path)
    assert max(rec.signals["input_left_hz"]) > 0
    assert max(rec.signals["gf_hz"]) > 0
    assert len(rec.spike_indices) > 0
    assert rec.meta["seed"] == 1 and rec.meta["config_hash"] == load_config().hash()


def test_out_of_arena_aborts_with_partial_recording(tmp_path):
    cfg = load_config()
    cfg.run.arena_radius_mm = 0.05
    r = run_scene(SHORT, cfg, ConstantController((1.2, 1.2)), tmp_path)
    assert r.status == "aborted" and r.reason == "out_of_arena"
    meta = read_recording(tmp_path).meta
    assert meta["n_frames"] == r.n_frames >= 1 and meta["status"] == "aborted"


def test_runaway_warning(tmp_path, fixture_connectome):
    cfg = load_config()
    cfg.run.runaway_active_neurons = 0
    ctrl = make_brain_controller(LOUD, cfg, fixture_connectome)
    assert "brain_runaway" in run_scene(LOUD, cfg, ctrl, tmp_path).warnings


def test_progress_reaches_one(tmp_path):
    seen = []
    run_scene(SHORT, load_config(), ConstantController((1, 1)), tmp_path, progress=seen.append)
    assert seen[-1] == pytest.approx(1.0) and seen == sorted(seen)


def test_fly_outside_arena_rejected_before_running(tmp_path):
    with pytest.raises(ValueError, match="arena"):
        scene = scene_with(fly={"pos": [100, 0]})
        run_scene(scene, load_config(), ConstantController((1, 1)), tmp_path)


def test_physics_blowup_mid_run_saves_aborted_recording(tmp_path, monkeypatch):
    import flybrain.loop as loop

    class ExplodingBody(loop.FlyBody):
        calls = 0

        def step(self, drive, n_steps):
            ExplodingBody.calls += 1
            if ExplodingBody.calls == 3:
                self.sim.physics.data.qvel[:] = 1e30
            return super().step(drive, n_steps)

    monkeypatch.setattr(loop, "FlyBody", ExplodingBody)
    r = run_scene(SHORT, load_config(), ConstantController((1, 1)), tmp_path)
    assert r.status == "aborted" and r.reason == "non_finite"
    meta = read_recording(tmp_path).meta
    assert meta["status"] == "aborted" and meta["n_frames"] == r.n_frames == 3


def test_controller_error_saves_aborted_recording_and_reraises(tmp_path):
    class Failing(ConstantController):
        n = 0

        def drive(self, t_s, body):
            Failing.n += 1
            if Failing.n == 3:
                raise RuntimeError("boom")
            return super().drive(t_s, body)

    with pytest.raises(RuntimeError, match="boom"):
        run_scene(SHORT, load_config(), Failing((1, 1)), tmp_path)
    meta = read_recording(tmp_path).meta
    assert meta["status"] == "aborted" and meta["reason"] == "error: RuntimeError: boom"
    assert meta["n_frames"] == 2


def test_threat_signal_is_at_frame_time(tmp_path, fixture_connectome):
    from flybrain.stimulus import threat_position

    ctrl = make_brain_controller(LOUD, load_config(), fixture_connectome)
    run_scene(LOUD, load_config(), ctrl, tmp_path)
    s = read_recording(tmp_path).signals
    # frame k shows the state at the end of interval k, i.e. t = (k + 1) * 0.02
    expected = threat_position(LOUD.shadow, 3 * 0.02)
    assert [s["threat_x"][2], s["threat_y"][2], s["threat_z"][2]] == pytest.approx(expected)


def test_meta_records_whether_a_brain_ran(tmp_path, fixture_connectome):
    run_scene(SHORT, load_config(), ConstantController((1, 1)), tmp_path / "nb")
    assert read_recording(tmp_path / "nb").meta["brain"] is False
    ctrl = make_brain_controller(SHORT, load_config(), fixture_connectome)
    run_scene(SHORT, load_config(), ctrl, tmp_path / "b")
    assert read_recording(tmp_path / "b").meta["brain"] is True
