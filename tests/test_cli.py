from typer.testing import CliRunner

from flybrain.cli import app
from flybrain.recording import read_recording

runner = CliRunner()


def test_run_no_brain(tmp_path):
    r = runner.invoke(
        app, ["run", "scenes/examples/no_threat.json", "--out", str(tmp_path), "--no-brain"]
    )
    assert r.exit_code == 0, r.output
    assert read_recording(tmp_path).meta["status"] == "complete"


def test_invalid_scene_exit_1(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"duration_s": 0}')
    r = runner.invoke(app, ["run", str(bad), "--out", str(tmp_path / "o"), "--no-brain"])
    assert r.exit_code == 1 and "duration_s" in r.output


def test_missing_data_exit_1(tmp_path):
    r = runner.invoke(
        app,
        [
            "run",
            "scenes/examples/loom_left.json",
            "--out",
            str(tmp_path),
            "--data-dir",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 1 and "download-data" in r.output


def test_aborted_run_exit_2(tmp_path):
    cfg = tmp_path / "tiny_arena.yaml"
    cfg.write_text("run:\n  arena_radius_mm: 0.05\n")
    r = runner.invoke(
        app,
        ["run", "scenes/examples/no_threat.json", "--out", str(tmp_path / "o"), "--no-brain",
         "--config", str(cfg)],
    )
    assert r.exit_code == 2 and "out_of_arena" in r.output
