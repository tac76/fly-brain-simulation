"""Command-line interface: `flybrain download-data`, `flybrain run`."""

from pathlib import Path
from typing import Annotated, NoReturn

import typer
from pydantic import ValidationError

from flybrain.config import load_config
from flybrain.connectome import Connectome, DataError, download_data
from flybrain.loop import ConstantController, make_brain_controller, run_scene
from flybrain.scene import load_scene

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _fail(message: str) -> NoReturn:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(1)


@app.command("download-data")
def download_data_cmd(data_dir: Annotated[Path, typer.Option()] = Path("data")) -> None:
    """Download and verify the FlyWire v783 files (CC BY-NC 4.0)."""
    try:
        download_data(data_dir)
    except DataError as e:
        _fail(str(e))
    typer.echo(f"data ready in {data_dir}")


@app.command()
def run(
    scene: Path,
    out: Annotated[Path, typer.Option(help="output folder for the recording")],
    config: Annotated[Path | None, typer.Option(help="config YAML")] = None,
    data_dir: Annotated[Path, typer.Option()] = Path("data"),
    device: Annotated[str, typer.Option(help="torch device for the brain")] = "cpu",
    no_brain: Annotated[bool, typer.Option(help="walk at base drive, no brain")] = False,
) -> None:
    """Simulate SCENE and write a recording to OUT."""
    try:
        sc = load_scene(scene)
        cfg = load_config(config)
        sc.validate_against(cfg)
    except (ValidationError, ValueError, OSError) as e:
        _fail(f"invalid scene or config: {e}")

    if no_brain:
        controller = ConstantController((cfg.motor.base_drive, cfg.motor.base_drive))
    else:
        try:
            connectome = Connectome.from_files(data_dir)
        except DataError as e:
            _fail(str(e))
        controller = make_brain_controller(sc, cfg, connectome, device=device)

    result = run_scene(sc, cfg, controller, out)
    per_s = result.wall_s / max(result.n_frames * 0.02, 1e-9)
    line = f"{result.status}: {result.n_frames} frames, wall {result.wall_s:.1f} s"
    line += f" ({per_s:.1f} s per simulated second)"
    if result.reason:
        line += f", reason: {result.reason}"
    if result.warnings:
        line += f", warnings: {', '.join(result.warnings)}"
    typer.echo(line)
    if result.status != "complete":
        raise typer.Exit(2)
