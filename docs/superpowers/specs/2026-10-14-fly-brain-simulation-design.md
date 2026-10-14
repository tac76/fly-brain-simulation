# Fly Brain Simulation: Design (v1)

Status: draft for review · Date: 2026-10-14 · Repo: `tac76/fly-brain-simulation`

## 1. Purpose

A browser-viewable 3D simulation in which a model of the **real fruit fly brain** (FlyWire
connectome, ~139k neurons) decides how a physically simulated fly escapes an approaching
threat. The project is a public portfolio piece: it must look impressive in the first ten
seconds (README GIF, live gallery) and hold up to a technical reader (honest claims, tests,
reproducible runs).

Audience: recruiters and engineers looking at the GitHub profile; secondary: anyone curious
about connectome simulation.

Success criteria for v1:
- A visitor opens the GitHub Pages gallery and watches, without installing anything, a fly
  escaping a looming object while the brain's spikes light up in 3D.
- A user with the repo runs the local editor, places a threat, presses **Apply**, and gets a
  new replay within minutes.
- Every claim in the README is backed by code and tests; hand-built parts are labelled.

## 2. Scope

### In v1
- One stimulus: a **looming object** (dark sphere: "hand", "bird", "swatter") moving along a
  user-defined path, with its shadow drawn on the ground for visual effect.
- Whole-brain leaky integrate-and-fire model on FlyWire v783 wiring (same equations and
  parameters as Shiu et al. 2024), implemented in PyTorch (CPU or GPU).
- Physically simulated body: FlyGym 1.2.x (NeuroMechFly v2, MuJoCo) with its
  `HybridTurningController` (CPG + recorded step kinematics + reflex rules).
- Brain–body closed loop, offline (not real time).
- Recording format, browser replay viewer, curated gallery on GitHub Pages.
- Local scene editor + job server (Apply flow), runnable via Docker.
- Tests and CI.

### Not in v1 (non-goals)
- Real-time / interactive-while-running control.
- Odor, taste, grooming or any second stimulus.
- Training or tuning of the brain model (see §12, v2).
- Realistic fly vision (rendered retina images, flyvis). Eye input is computed from geometry.
- Flight. The fly only walks.
- Collidable obstacles. Physics ground is flat; props are visual only.

### Feasibility evidence (spike, 2026-10-14)
Throwaway spike at `~/work/fly-brain-spike/` (VPS), not reused:
- Looming input to LPLC2 + LC4 of one eye drives the giant fiber (DNp01) at ~165–236 Hz
  (stronger ipsilateral), other escape DNs (DNp02, DNp04, DNp11), and **contralateral**
  steering DNs DNa01/DNa02, i.e. a "turn away" signal. No input: brain silent. Threshold:
  ≥ ~10–30 Hz input needed.
- Odor input floods the model (~10k active neurons) with no left/right or intensity
  information; this is a property of the published model (cross-checked against the original
  Brian2 code). Hence no odor in v1.
- FlyGym 1.2.1 walks, steers and renders headless on the VPS. FlyGym 2.x no longer ships the
  turning controller.
- Cost on one VPS core: brain ~10–20 s, physics ~30 s per simulated second. GPU not yet
  measured.

## 3. Architecture

```
[Browser: editor] --scene.json--> [server (FastAPI)] --job--> [simulation loop]
        ^                                                           |
        +------------- [Browser: viewer] <---- recording folder <---+
```

Python package `flybrain` with one job per module:

| Module | Responsibility | Depends on |
|---|---|---|
| `flybrain.connectome` | download/load FlyWire v783 connectivity + annotations; name→index lookup by cell type and side | pandas, pyarrow |
| `flybrain.brain` | LIF network state and `step(n_steps, input_rates) -> spike counts`; CPU/GPU | torch, `connectome` |
| `flybrain.stimulus` | scene geometry → per-eye looming input rates | numpy |
| `flybrain.body` | FlyGym wrapper: reset, `step(drive, n_steps)`, body-part world poses | flygym 1.2.x |
| `flybrain.motor` | descending-neuron rates → `[drive_left, drive_right]` | numpy |
| `flybrain.loop` | runs a scene end to end, emits frames and progress | all above |
| `flybrain.recording` | write/read the recording format, schema version | numpy |
| `flybrain.scene` | scene schema and validation | pydantic |
| `flybrain.config` | all calibration constants in one versioned YAML | pydantic |

Outside the package: `server/` (FastAPI job queue), `viewer/` (Vite + TypeScript + three.js),
`scripts/` (data download, mesh export, gallery build).

Each module is usable and testable alone. The viewer only depends on the recording format.

## 4. Simulation loop

- Physics timestep and brain timestep: **0.1 ms**.
- Exchange interval: **20 ms** (200 steps each). Per interval:
  1. `stimulus`: object position vs. fly head pose → per-eye input rate (held constant over the
     interval).
  2. `brain.step(200, rates)` → spike counts of all neurons in the interval.
  3. `motor`: smoothed DN rates → drives.
  4. `body.step(drive, 200)`.
  5. Emit one recording frame (50 fps).
- Brain and body alternate sequentially (no threading in v1).
- Deterministic: one seed controls Poisson input and any physics randomness. Same scene + seed +
  config + package version = identical recording.
- Max scene duration in v1: 10 s.

### 4.1 Stimulus encoding (`flybrain.stimulus`)
- Object: sphere of radius `r`, position along a polyline path at constant speed.
- Per eye (left/right eye centre offset from the head body): distance `d`, visual angle
  `θ = 2·atan(r/d)`, expansion rate `θ̇`, azimuth in the fly frame.
- Eye weighting by azimuth: object on the left mostly drives the left eye, with an overlap zone
  in front.
- Rate for the eye's LPLC2 + LC4 population:
  `rate = r_max · clip((θ̇ − θ̇_0) / (θ̇_sat − θ̇_0), 0, 1) · w_eye`, gated by `θ > θ_min`.
  Defaults: `r_max = 150 Hz`; the other constants are calibrated (see §4.3).
- No occlusion in v1.

### 4.2 Motor mapping (`flybrain.motor`)
- DN rates per interval, smoothed with an exponential filter (τ = 50 ms).
- Turn signal: `turn = k_turn · ((DNa01_R + DNa02_R) − (DNa01_L + DNa02_L))`.
- Escape boost: `boost = k_gf · mean(DNp01_L, DNp01_R)`, saturating.
- Drives: `base·(1 + boost)` per side, with `turn` added to one side and subtracted from the
  other, then clamped to a stable range found in calibration.
- Default state with a silent brain: steady slow walking (`base`). The README states that
  baseline walking is a default, not a brain decision.
- The sign convention (which side's DNa activity turns the fly which way) is fixed by a test
  that compares against the biology (DNa02 activity on one side → turn to that side) and the
  spike result (loom on the left → right-side DNa → turn away).

### 4.3 Calibration
A script runs a fixed set of scenes and writes the chosen constants to `config/default.yaml`.
Target behaviour: no reaction to a slow, distant object; clear turn-away and speed-up for a fast
approach from either side. Constants and the reasoning behind them go in `docs/calibration.md`.

## 5. Recording format

One folder per run, version field in `meta.json` (`format_version: 1`).

| File | Content |
|---|---|
| `meta.json` | scene, seed, config hash, package version, fps, duration, body-part names, status (`complete` / `aborted` + reason), warnings |
| `body.bin` | float32, per frame per body part: position (3) + quaternion (4) |
| `spikes.bin` | sparse: per frame the indices (uint32) of neurons that spiked, with offsets |
| `signals.json` | per frame: object position, per-eye input rate, key DN rates, drives |

Shared assets, generated once by scripts:
- `brain_points.bin`: 3D position and cell-type id of every neuron in the model, plus the
  index lists of highlighted neurons (LPLC2, LC4, DNp01, DNa01, DNa02).
- Fly meshes exported from FlyGym to glTF.

Expected size: ~3–7 MB per 10 s run. Writer and reader live in `flybrain.recording`; the
TypeScript reader in the viewer mirrors it.

## 6. Viewer (static web app)

- **Gallery**: list of curated runs with thumbnail and one-line description.
- **3D scene**: fly (meshes driven by `body.bin`), tabletop environment (visual props, lighting),
  the looming object, and its ground shadow. Orbit camera plus a follow camera.
- **Brain panel**: point cloud of all ~139k neurons at their real positions. Spikes flash and
  fade. Highlighted neurons are labelled (input: LPLC2/LC4; output: giant fiber, DNa01/DNa02).
- **Charts**: input rate per eye, key DN rates, left/right drive, synced to the timeline.
- **Playback**: play/pause, scrub, speed 0.1×–2×.
- **"How it works" overlay**: plain-language explanation of which parts are the brain model and
  which are hand-built (stimulus encoding, motor mapping, gait controller).

Tech: Vite, TypeScript, three.js. No backend in gallery mode. Must run in current Chrome,
Firefox and Safari on a mid-range laptop.

## 7. Editor and server (local only)

- Editor (same web app, "local mode"): set the fly start position and heading, place the object
  path (2–4 waypoints with height), size, speed, duration (≤ 10 s), seed; press **Apply**.
- Server (FastAPI): `POST /jobs` (scene JSON) → validates, queues; `GET /jobs/{id}` →
  status and progress; `GET /recordings/{id}/…` → files. One job at a time.
- On completion the editor opens the replay.
- Docker image bundles Python, the package, the server and the built viewer. GPU optional.

## 8. Error handling

- Invalid scene: rejected by validation before any simulation, with a message per field.
- Fly flips over, leaves the arena or physics produces NaN: run stops, recording saved with
  `status: aborted` and the reason; partial replay works.
- Brain runaway (active-neuron count above a threshold): warning stored in `meta.json` and
  shown in the viewer.
- Job crash: error and log tail shown in the editor; the server keeps running.
- Missing data files: a clear message pointing to `scripts/download_data.py`.

## 9. Testing

| Area | Test | Runs |
|---|---|---|
| brain | small hand-built network with known spike output | CI |
| brain | real connectome: silent without input; looming input → DNp01 active, contralateral DNa bias | manual / PC (marked `slow`) |
| brain | parity with the published model: active-neuron counts for the spike's reference stimuli within tolerance | manual (`slow`) |
| stimulus | geometry: angle, expansion, eye weighting for known positions | CI |
| motor | mapping, sign convention, clamping | CI |
| body | a few hundred steps without crash; poses finite | CI |
| loop | determinism: 1 s scene twice → byte-identical recording | CI (small fixture network) |
| recording | write → read round trip; version check | CI |
| scene | validation accepts good and rejects bad scenes | CI |
| server | job lifecycle with a stub simulator | CI |
| viewer | lint, type-check, build; Playwright loads a gallery run and screenshots it | CI |

CI: GitHub Actions on every push; status badge in the README. CI does not download the full
connectome; it uses a small fixture network.

## 10. Repository layout

```
fly-brain-simulation/
  flybrain/            Python package (§3)
  server/              FastAPI app
  viewer/              Vite + TypeScript + three.js
  config/default.yaml  calibration constants
  scenes/gallery/      curated scene files
  recordings/gallery/  their recordings (committed)
  data/                downloaded FlyWire files (git-ignored)
  scripts/             download_data.py, export_meshes.py, build_gallery.py, calibrate.py
  tests/
  docs/                this spec, plans, calibration.md, architecture diagram
  Dockerfile  pyproject.toml  README.md  LICENSE  DATA_LICENSE.md  NOTICE
```

Tooling: Python 3.12, uv, ruff, pytest; Node LTS, npm, eslint, Playwright.

## 11. Licensing and attribution

- Code: MIT.
- FlyWire data: CC BY-NC 4.0 (non-commercial, attribution). Not committed; downloaded by
  script. Derived files (`brain_points.bin`, gallery recordings) are published under
  CC BY-NC 4.0 and listed in `DATA_LICENSE.md`.
- FlyGym (Apache-2.0) and its meshes: attribution in `NOTICE`.
- Published brain model (Shiu et al., MIT): re-implemented; cited.
- README cites: FlyWire (Dorkenwald et al. 2024; Schlegel et al. 2024), Shiu et al. 2024,
  NeuroMechFly v2 (Wang-Chen et al. 2024). Related work: DesktopFly
  (`DenisSergeevitch/desktop-fly`), with a short note on how this project differs (full
  ~139k-neuron model, physics-simulated body, browser, reproducible experiment runs).

## 12. Outlook: v2 (direction only, not specified)

v2's highlight is **connectome-constrained training**: keep the FlyWire wiring (who connects
to whom, and the sign), learn only a small set of parameters (e.g. one gain per cell-type pair)
so the fly performs a behaviour the untrained model cannot, e.g. steering toward an odor.
Prerequisite: fix the odor runaway (global tuning, adaptation). Precedent: Lappalainen et al.
2024 (visual system). v1 is built so that v2 slots in: `brain` exposes its parameters as
torch tensors, and the stimulus/motor interfaces are per-stimulus modules. v2 gets its own
spec.

## 13. Development workflow

- Code lives on the VPS (`~/work/fly-brain-simulation`); heavy runs (calibration, gallery
  recordings, GPU timing) on the PC.
- Commits authored as `tac76` (GitHub noreply address) so they count on the profile.
- The GitHub repo is created and made public once the first milestone runs end to end.

## 14. Risks

| Risk | Mitigation |
|---|---|
| Brain output too noisy for a clean escape after closing the loop | Calibration (§4.3); smoothing; first milestone is a brain-only check against the spike numbers |
| Simulation too slow for an acceptable Apply wait | GPU brain; 10 s cap; measure on PC early; shorter default scenes |
| Fly falls over at high drives | clamp range from calibration; aborted-run handling |
| Exporting body poses and meshes from FlyGym to the browser is harder than expected | early milestone that replays a hand-driven walk (no brain) in the viewer |
| Looks like DesktopFly | different stack and claims (see §11); v2 training as the distinct highlight |
