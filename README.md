# Fly Brain Simulation

A model of the real fruit fly brain (FlyWire connectome, ~139k neurons) decides how a
physically simulated fly escapes a looming threat.

**Status:** work in progress. The simulation core runs; the 3D browser viewer is next.

## How it works

Every 20 ms the simulation:

1. computes how large and how fast-growing the threat looks to each eye, and turns that into
   input for the brain's looming-detector neurons (LPLC2, LC4) — *hand-built encoding*;
2. runs the whole-brain spiking model (FlyWire v783 wiring, equations of Shiu et al. 2024);
3. reads the descending neurons: steering (DNa01/DNa02) and escape (giant fiber, DNp01);
4. turns them into two walking drives — *hand-built mapping*;
5. steps the physically simulated body (FlyGym / NeuroMechFly, MuJoCo), whose legs are moved by
   a built-in gait controller.

The decision to turn away and run comes from the brain model; stimulus encoding, motor mapping
and the gait are hand-built and labelled as such.

## Quick start

```bash
uv sync
uv run flybrain download-data          # ~135 MB, FlyWire data (CC BY-NC 4.0)
uv run flybrain run scenes/examples/loom_left.json --out out/loom_left
uv run flybrain run scenes/examples/no_threat.json --out out/walk --no-brain   # no data needed
```

`flybrain run` writes a recording folder (format: [docs/recording-format.md](docs/recording-format.md)).

## Development

```bash
uv run pytest -m "not slow"   # fast suite (CI)
uv run pytest -m slow         # needs data/: checks against the published model
uv run ruff check .
```

## Data and credits

- Connectome: FlyWire (Dorkenwald et al. 2024; Schlegel et al. 2024), CC BY-NC 4.0 —
  downloaded by script, not part of this repository.
- Brain model equations and parameters: Shiu et al. 2024, *A Drosophila computational brain
  model reveals sensorimotor processing*, Nature.
- Body: NeuroMechFly v2 / FlyGym (Wang-Chen et al. 2024), Apache-2.0.

Code: MIT.
