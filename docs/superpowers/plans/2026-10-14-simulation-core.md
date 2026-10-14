# Simulation Core Implementation Plan (Plan 1 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python package `flybrain` and CLI that run a looming-threat scene through the FlyWire whole-brain LIF model and the FlyGym body in closed loop and write a replayable recording.

**Architecture:** Small single-purpose modules (`config`, `scene`, `connectome`, `brain`, `stimulus`, `motor`, `body`, `recording`, `loop`, `cli`) per spec §3. The loop alternates 20 ms of brain and 20 ms of physics and emits one frame per interval. A `Controller` protocol lets the loop run with the brain or with a constant drive (needed by Plan 2 before the brain is calibrated).

**Tech Stack:** Python 3.12, uv, PyTorch (CPU build in this plan), FlyGym 1.2.1 (MuJoCo), numpy, pandas, pyarrow, pydantic v2, PyYAML, Typer, pytest, ruff, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-14-fly-brain-simulation-design.md`

**Plans:** 1 = simulation core (this). 2 = viewer + gallery assets (mesh export, brain points, replay). 3 = editor/server, Docker, calibration, gallery, README, publish. Plans 2 and 3 are written when Plan 1 is done.

## Global Constraints

- Python `>=3.12,<3.13`; dependency `flygym[examples]==1.2.1` (2.x lacks `HybridTurningController`); `networkx` must be installed (flygym examples import it).
- Torch from the PyTorch CPU index on Linux in this plan (`https://download.pytorch.org/whl/cpu`, uv explicit index). GPU setup is Plan 3.
- Units: length mm, time s in public APIs, ms only inside `brain`. Coordinates: FlyGym world frame, z up, fly at heading 0 faces +x.
- Physics timestep `1e-4` s; brain `dt = 0.1` ms; exchange interval 20 ms = 200 steps; recording 50 fps; frames per run = `floor(duration_s / 0.02)`.
- Brain parameters exactly as Shiu et al. 2024 (`Drosophila_brain_model/model.py`): `v_0 = v_rst = -52 mV`, `v_th = -45 mV`, `t_mbr = 20 ms`, `tau = 5 ms`, `t_rfc = 2.2 ms`, `t_dly = 1.8 ms` (18 steps), `w_syn = 0.275 mV` per signed synapse count, Poisson kick `= 250 × w_syn = 68.75 mV` added to `v`, Poisson targets have no refractory period.
- Neuron index = row order of `Completeness_783.csv`; this index is used everywhere (brain, recording spikes, Plan 2 brain points).
- Data (CC BY-NC 4.0) lives in `data/` (git-ignored) and is never committed.
- Determinism: same scene + seed + config + package version + device type `cpu` ⇒ byte-identical recording files. GPU runs are not required to be byte-identical (CUDA `index_add_` uses atomics).
- Commits authored as `tac76 <217262554+tac76@users.noreply.github.com>` (already set in repo config). Conventional commit messages, English.
- Tests: `pytest -m "not slow"` must pass in CI without the connectome download; tests needing `data/` are marked `@pytest.mark.slow`.

## Review Focus

1. Threat path passing through or touching the fly (`d → 0`): visual angle must clamp to 180°, no division by zero or NaN rates → test in Task 5.
2. Scene whose path goes below the ground, has duplicate consecutive waypoints, or starts outside the arena → rejected by validation with a per-field message → tests in Task 2.
3. Fly leaves the arena or flips mid-run → run stops, recording saved with `status: aborted` and a readable partial replay → test in Task 9.
4. `duration_s` not a multiple of 20 ms (e.g. 1.01) → frame count `floor(duration/0.02)`, no partial frame → test in Task 9.
5. Missing or corrupted data files → `DataError` naming the file and pointing to `flybrain download-data` (checksum mismatch included) → test in Task 3.

---

### Task 1: Project scaffold and CI

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `LICENSE` (MIT, "tac76", 2026), `README.md` (title + one line + "work in progress"), `flybrain/__init__.py` (`__version__ = "0.1.0"`), `tests/test_package.py`, `.github/workflows/ci.yml`

**Interfaces:**
- Produces: installable package `flybrain`, console script `flybrain = flybrain.cli:app` (module created in Task 10; until then the entry point may fail to import, which is fine), pytest marker `slow`.

- [ ] **Step 1: Write `tests/test_package.py`**

```python
import flybrain

def test_version():
    assert flybrain.__version__ == "0.1.0"
```

- [ ] **Step 2: Write `pyproject.toml`**: hatchling build; deps `numpy`, `pandas`, `pyarrow`, `torch`, `flygym[examples]==1.2.1`, `networkx`, `pydantic>=2`, `pyyaml`, `typer`; dev group `pytest`, `ruff`; `[tool.pytest.ini_options] markers = ["slow: needs downloaded FlyWire data or long runtime"]`; ruff line length 100; uv index `pytorch-cpu` (explicit) used for `torch` on Linux. `.gitignore`: `data/`, `.venv/`, `__pycache__/`, `out/`, `*.egg-info`.

- [ ] **Step 3: Install and run**

Run: `uv sync && uv run pytest -q && uv run ruff check .`
Expected: `1 passed`, ruff clean. `uv run python -c "import torch; print(torch.__version__)"` shows a `+cpu` build.

- [ ] **Step 4: Write `.github/workflows/ci.yml`**: on push and pull_request; ubuntu-latest; `astral-sh/setup-uv`; `uv sync`; `uv run ruff check .`; `uv run pytest -m "not slow" -q`.

- [ ] **Step 5: Commit** `chore: scaffold package, tooling and CI`

---

### Task 2: Config and scene models

**Files:**
- Create: `flybrain/config.py`, `config/default.yaml`, `flybrain/scene.py`, `scenes/examples/loom_left.json`, `tests/test_config.py`, `tests/test_scene.py`

**Interfaces:**
- Produces:
  - `class StimulusConfig(BaseModel)`: `r_max_hz: float = 150`, `theta_min_deg: float = 5`, `theta_dot_0_deg_s: float = 20`, `theta_dot_sat_deg_s: float = 300`, `overlap_deg: float = 20`
  - `class MotorConfig(BaseModel)`: `base_drive: float = 0.7`, `tau_ms: float = 50`, `k_turn: float = 0.01`, `k_gf: float = 0.01`, `boost_max: float = 0.8`, `drive_min: float = 0.0`, `drive_max: float = 1.5`
  - `class RunConfig(BaseModel)`: `arena_radius_mm: float = 60`, `runaway_active_neurons: int = 5000`
  - `class Config(BaseModel)`: `stimulus`, `motor`, `run`; `def hash(self) -> str` (sha256 of canonical JSON, first 12 hex chars)
  - `def load_config(path: Path | None = None) -> Config` (None ⇒ `config/default.yaml`)
  - `class Scene(BaseModel)` mirroring spec §4 JSON: `duration_s` (0 < d ≤ 10), `seed: int ≥ 0`, `fly: FlyStart(pos: tuple[float, float], heading_deg: float)`, `shadow: Threat(size_mm > 0` = diameter, `speed_mm_s > 0`, `path: list[tuple[float,float,float]]` with 2–4 points`)`, `environment: Literal["tabletop"]`
  - `def load_scene(path: Path) -> Scene`; `Scene.validate_against(config: Config) -> None` raises `ValueError` if fly start is outside `arena_radius_mm`.
  - All constants marked "calibrated in Plan 3" in a YAML comment.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scene.py
def test_example_scene_loads():
    s = load_scene(Path("scenes/examples/loom_left.json"))
    assert s.duration_s == 3 and len(s.shadow.path) == 2

@pytest.mark.parametrize("patch,field", [
    ({"duration_s": 0}, "duration_s"),
    ({"duration_s": 10.5}, "duration_s"),
    ({"shadow": {"path": [[0, 0, 5]]}}, "path"),                 # < 2 points
    ({"shadow": {"path": [[0, 0, 5]] * 5}}, "path"),             # > 4 points
    ({"shadow": {"path": [[10, 0, -1], [0, 0, 3]]}}, "path"),    # below ground (z < 0)
    ({"shadow": {"path": [[10, 0, 3], [10, 0, 3]]}}, "path"),    # duplicate consecutive points
    ({"shadow": {"size_mm": 0}}, "size_mm"),
    ({"environment": "space"}, "environment"),
])
def test_invalid_scene_rejected(patch, field):
    with pytest.raises(ValidationError) as e:
        Scene.model_validate(deep_merge(EXAMPLE, patch))
    assert field in str(e.value)

def test_fly_outside_arena_rejected():
    s = Scene.model_validate(deep_merge(EXAMPLE, {"fly": {"pos": [100, 0]}}))
    with pytest.raises(ValueError, match="arena"):
        s.validate_against(load_config())
```

```python
# tests/test_config.py
def test_default_config_loads_and_hash_is_stable():
    a, b = load_config(), load_config()
    assert a.stimulus.r_max_hz == 150 and a.hash() == b.hash() and len(a.hash()) == 12
```

`EXAMPLE` = contents of `scenes/examples/loom_left.json`; `deep_merge` is a small test helper.

- [ ] **Step 2: Run** `uv run pytest tests/test_scene.py tests/test_config.py -q` → FAIL (import errors).
- [ ] **Step 3: Implement** models in `flybrain/config.py` and `flybrain/scene.py`; `scenes/examples/loom_left.json`: `duration_s: 3`, `seed: 1`, fly at `[0, 0]` heading 0, threat diameter 8 mm, 40 mm/s, path `[[0, 30, 10], [0, 0, 3]]` (approaches from the fly's left).
- [ ] **Step 4: Run** same command → PASS.
- [ ] **Step 5: Commit** `feat: add config and scene models with validation`

---

### Task 3: Connectome data and loader

**Files:**
- Create: `flybrain/connectome.py`, `tests/conftest.py` (fixture connectome), `tests/test_connectome.py`

**Interfaces:**
- Produces:
  - `DATA_FILES: dict[str, tuple[str, str]]`: name → (pinned URL, sha256):
    - `Completeness_783.csv`: `https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/91bdd1e7dcf193f3e7ca5a8933497fcef63b7960/Completeness_783.csv`, `bbb847a4cc2caaa7a16349722d220c087317b946d148d4d592d94d250617a311`
    - `Connectivity_783.parquet`: same repo/commit, `efeb23fb99098e9c390f6869969b2a121a2ee92c833cfc45ecb2c1d8e1af0347`
    - `neuron_annotations.tsv`: `https://raw.githubusercontent.com/flyconnectome/flywire_annotations/a83b2776d60d5764cef36b927f5f9679c16c47a2/supplemental_files/Supplemental_file1_neuron_annotations.tsv`, `b214970b55d2fbe0853bba536fdcb9e28730f4eb7ab06f600491df795da683cd`
  - `def download_data(data_dir: Path) -> None` (skips files whose checksum matches; streams; verifies)
  - `class DataError(Exception)`
  - `@dataclass(frozen=True) class Connectome`: `n: int`, `root_ids: np.ndarray[int64]`, `pre_indptr: np.ndarray[int64]` (len n+1), `post_idx: np.ndarray[int32]`, `weight_syn: np.ndarray[float32]` (signed synapse count, pre-major CSR), `cell_type: np.ndarray[object]`, `side: np.ndarray[object]`
    - `@classmethod from_files(cls, data_dir: Path) -> Connectome` (raises `DataError` with file name + "run `flybrain download-data`" for a missing file or checksum mismatch; checksum checked on load)
    - `@classmethod from_edges(cls, n, pre, post, weight, cell_type=None, side=None, root_ids=None) -> Connectome` (for fixtures)
    - `def indices(self, cell_type: str, side: str | None = None) -> np.ndarray[int64]` (raises `KeyError` if no match)
  - Annotation join: `root_id` → index; neurons without annotation get `cell_type=""`, `side=""` (≈0.4 % of neurons).
  - `tests/conftest.py` fixture `tiny_connectome`: 6 neurons: 0→1 strong excitatory, 1→2 strong excitatory, 3→4 strong inhibitory, 5 isolated; cell types `["IN_L","MID","OUT","IN_R","OUTR","ISO"]`.

- [ ] **Step 1: Write failing tests**

```python
def test_from_edges_builds_pre_major_csr(tiny_connectome):
    c = tiny_connectome
    assert c.n == 6 and c.pre_indptr[0] == 0 and c.pre_indptr[-1] == len(c.post_idx)
    s, e = c.pre_indptr[0], c.pre_indptr[1]
    assert list(c.post_idx[s:e]) == [1]

def test_indices_by_type(tiny_connectome):
    assert list(tiny_connectome.indices("OUT")) == [2]
    with pytest.raises(KeyError):
        tiny_connectome.indices("NOPE")

def test_missing_file_raises_data_error(tmp_path):
    with pytest.raises(DataError, match="Completeness_783.csv.*download-data"):
        Connectome.from_files(tmp_path)

def test_corrupt_file_raises_data_error(tmp_path):
    for name in DATA_FILES: (tmp_path / name).write_text("x")
    with pytest.raises(DataError, match="checksum"):
        Connectome.from_files(tmp_path)

@pytest.mark.slow
def test_real_connectome():
    c = Connectome.from_files(Path("data"))
    assert c.n == 138639 and len(c.post_idx) == 15091983
    assert len(c.indices("LPLC2", "left")) > 90 and len(c.indices("DNp01", "left")) == 1
```

- [ ] **Step 2: Run** `uv run pytest tests/test_connectome.py -q -m "not slow"` → FAIL.
- [ ] **Step 3: Implement** `flybrain/connectome.py` (CSR via `np.argsort(pre, kind="stable")` + `np.bincount`; use column `Excitatory x Connectivity`).
- [ ] **Step 4: Run** → PASS. Then `uv run python -c "from flybrain.connectome import download_data; download_data(__import__('pathlib').Path('data'))"` and `uv run pytest tests/test_connectome.py -q -m slow` → PASS.
- [ ] **Step 5: Commit** `feat: add connectome download and loader`

---

### Task 4: LIF brain (PyTorch)

**Files:**
- Create: `flybrain/brain.py`, `tests/test_brain.py`

**Interfaces:**
- Consumes: `Connectome` (Task 3).
- Produces:
  - `@dataclass class BrainParams` with the Shiu values from Global Constraints (`dt_ms = 0.1`).
  - `class LIFBrain`:
    - `__init__(self, connectome: Connectome, params: BrainParams = BrainParams(), device: str = "cpu", seed: int = 0)`
    - `reset(self, seed: int) -> None` (state to rest, clears delay buffer, reseeds `torch.Generator` on CPU)
    - `step(self, n_steps: int, input_rates: dict[int, float]) -> np.ndarray` returns int32 spike counts per neuron (length `n`) for these steps
    - `last_spiking(self) -> np.ndarray` int64 indices of neurons that spiked at least once in the last `step` call
- Algorithm (event-driven, decided here because the dense alternative is ~10× slower on CPU):
  - State tensors `v`, `g`, `rfc_steps` (int), delay ring buffer `buf` of shape `(18, n)`.
  - Per step `k`: `g += buf[k % 18]; buf[k % 18] = 0`; for non-refractory neurons `v = v0 + (v - v0)·exp(-dt/t_mbr) + g·(1 - exp(-dt/t_mbr))`, `g *= exp(-dt/tau)`; decrement refractory counters; Poisson hits (`rand < rate·dt`) add 68.75 mV to `v`; `spk = (v > v_th)`; for spikers: count, `v = v_rst`, `g = 0`, `rfc = 22` steps except Poisson targets (0); deliver: gather the CSR segments of `spk` (`repeat_interleave` of segment lengths + offsets) and `buf[k % 18].index_add_(0, post_idx[seg], weight_syn[seg] · w_syn)`.
  - Delivery into the slot just read makes the spike arrive 18 steps (1.8 ms) later.

- [ ] **Step 1: Write failing tests**

```python
def test_silent_without_input(tiny_connectome):
    b = LIFBrain(tiny_connectome); assert b.step(2000, {}).sum() == 0

def test_excitatory_chain_propagates(tiny_connectome):
    b = LIFBrain(tiny_connectome, seed=1)
    c = b.step(5000, {0: 100.0})          # 0.5 s at 100 Hz
    assert c[0] > 20 and c[1] > 0 and c[2] > 0 and c[5] == 0

def test_inhibitory_input_does_not_cause_spikes(tiny_connectome):
    c = LIFBrain(tiny_connectome).step(5000, {3: 100.0})
    assert c[3] > 20 and c[4] == 0

def test_synaptic_delay(tiny_connectome):
    # first spike of neuron 1 occurs >= 18 steps after first spike of neuron 0
    b = LIFBrain(tiny_connectome, seed=2)
    first = {0: None, 1: None}
    for k in range(3000):
        b.step(1, {0: 200.0})
        for i in first:
            if first[i] is None and i in b.last_spiking(): first[i] = k
    assert first[1] - first[0] >= 18

def test_deterministic_on_cpu(tiny_connectome):
    a = LIFBrain(tiny_connectome, seed=7).step(3000, {0: 80.0})
    b = LIFBrain(tiny_connectome, seed=7).step(3000, {0: 80.0})
    assert np.array_equal(a, b)

@pytest.mark.slow
def test_real_brain_looming_matches_spike():
    c = Connectome.from_files(Path("data"))
    b = LIFBrain(c, seed=0)
    inp = {int(i): 150.0 for t in ("LPLC2", "LC4") for i in c.indices(t, "left")}
    counts = b.step(5000, inp)                      # 0.5 s
    assert 670 <= (counts > 0).sum() <= 910         # Brian2 reference: 790 (±15 %)
    gf_l, = c.indices("DNp01", "left")
    assert counts[gf_l] / 0.5 > 100                 # giant fiber strongly active
    dna_r = sum(counts[c.indices(t, "right")].sum() for t in ("DNa01", "DNa02"))
    dna_l = sum(counts[c.indices(t, "left")].sum() for t in ("DNa01", "DNa02"))
    assert dna_r > dna_l                            # contralateral steering bias
```

The fixture weights in `conftest.py` must be chosen so one presynaptic spike reliably drives the postsynaptic neuron (e.g. 60 synapses × 0.275 mV); `test_excitatory_chain_propagates` pins that.

- [ ] **Step 2: Run** `uv run pytest tests/test_brain.py -q -m "not slow"` → FAIL.
- [ ] **Step 3: Implement** `flybrain/brain.py`.
- [ ] **Step 4: Run** → PASS; then `-m slow` → PASS. Record wall time per simulated second in the commit message body.
- [ ] **Step 5: Commit** `feat: add event-driven LIF whole-brain model`

---

### Task 5: Looming stimulus encoder

**Files:**
- Create: `flybrain/stimulus.py`, `tests/test_stimulus.py`

**Interfaces:**
- Consumes: `StimulusConfig`, `Threat` (Task 2).
- Produces:
  - `def threat_position(threat: Threat, t_s: float) -> np.ndarray` (3,), constant speed along the polyline, stays at the last point after arrival.
  - `def visual_angle(radius_mm: float, distance_mm: float) -> float` radians, `2·atan(r/d)`, returns π when `d <= r`.
  - `def eye_weights(azimuth_rad: float, overlap_deg: float) -> tuple[float, float]` (left, right): `w_left = clip(0.5 + sin(az) / (2·sin(overlap)), 0, 1)`, `w_right = 1 - w_left`. Azimuth positive = fly's left.
  - `class LoomingEncoder`:
    - `__init__(self, cfg: StimulusConfig, threat: Threat, interval_s: float = 0.02)`
    - `rates(self, t_s: float, eye_left: np.ndarray, eye_right: np.ndarray, head: np.ndarray, forward: np.ndarray) -> tuple[float, float]` input rate (Hz) for left and right eye populations. Per eye: θ from that eye's distance, `θ̇ = (θ − θ_prev)/interval` (0 on first call), `rate = r_max·clip((θ̇−θ̇0)/(θ̇sat−θ̇0), 0, 1)·w_eye` if `θ > θ_min` else 0. Azimuth from head→threat vector projected on the ground plane relative to `forward`.
    - `last_theta_deg: tuple[float, float]` for signals.

- [ ] **Step 1: Write failing tests**

```python
def test_eye_weights():
    assert eye_weights(math.pi/2, 20) == pytest.approx((1.0, 0.0))
    assert eye_weights(0.0, 20) == pytest.approx((0.5, 0.5))
    assert eye_weights(-math.pi/2, 20) == pytest.approx((0.0, 1.0))
    assert eye_weights(math.pi, 20) == pytest.approx((0.5, 0.5))       # directly behind

def test_visual_angle_clamps_at_contact():
    assert visual_angle(4, 0.0) == pytest.approx(math.pi)
    assert visual_angle(4, 2.0) == pytest.approx(math.pi)
    assert visual_angle(1, 1e6) == pytest.approx(2e-6, rel=1e-3)

def test_threat_position_constant_speed_and_stop():
    th = Threat(size_mm=8, speed_mm_s=10, path=[(0, 0, 0), (10, 0, 0), (10, 10, 0)])
    assert threat_position(th, 0.5) == pytest.approx([5, 0, 0])
    assert threat_position(th, 1.5) == pytest.approx([10, 5, 0])
    assert threat_position(th, 99) == pytest.approx([10, 10, 0])

def test_fast_approach_from_left_drives_left_eye_only():
    enc = LoomingEncoder(StimulusConfig(), Threat(size_mm=8, speed_mm_s=200, path=[(0, 30, 2), (0, 1, 2)]))
    eyes = dict(eye_left=np.array([0, .2, 1.]), eye_right=np.array([0, -.2, 1.]),
                head=np.array([0, 0, 1.]), forward=np.array([1., 0, 0]))
    out = [enc.rates(t, **eyes) for t in np.arange(0, 0.14, 0.02)]
    assert out[0] == (0.0, 0.0)
    assert max(l for l, _ in out) > 100 and max(r for _, r in out) < 1e-6

def test_slow_distant_threat_no_input():
    enc = LoomingEncoder(StimulusConfig(), Threat(size_mm=2, speed_mm_s=1, path=[(50, 0, 2), (40, 0, 2)]))
    eyes = dict(eye_left=np.array([0, .2, 1.]), eye_right=np.array([0, -.2, 1.]),
                head=np.array([0, 0, 1.]), forward=np.array([1., 0, 0]))
    assert all(enc.rates(t, **eyes) == (0.0, 0.0) for t in np.arange(0, 1, 0.02))

def test_threat_through_fly_gives_finite_rates():
    enc = LoomingEncoder(StimulusConfig(), Threat(size_mm=8, speed_mm_s=100, path=[(0, 5, 1), (0, -5, 1)]))
    eyes = dict(eye_left=np.array([0, .2, 1.]), eye_right=np.array([0, -.2, 1.]),
                head=np.array([0, 0, 1.]), forward=np.array([1., 0, 0]))
    for t in np.arange(0, 0.2, 0.02):
        l, r = enc.rates(t, **eyes)
        assert math.isfinite(l) and math.isfinite(r) and 0 <= l <= 150 and 0 <= r <= 150
```

- [ ] **Step 2: Run** `uv run pytest tests/test_stimulus.py -q` → FAIL.
- [ ] **Step 3: Implement** `flybrain/stimulus.py` (threat radius = `size_mm / 2`).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: add looming stimulus encoder`

---

### Task 6: Motor mapping

**Files:**
- Create: `flybrain/motor.py`, `tests/test_motor.py`

**Interfaces:**
- Consumes: `MotorConfig`.
- Produces:
  - `@dataclass class DNRates`: `dna_left: float`, `dna_right: float` (sum of DNa01 + DNa02 per side, Hz), `gf: float` (mean DNp01 L/R, Hz)
  - `class MotorMapper`:
    - `__init__(self, cfg: MotorConfig, interval_ms: float = 20)`
    - `update(self, rates: DNRates) -> np.ndarray` shape (2,) `[drive_left, drive_right]`
    - `smoothed: DNRates` (after EMA, for signals)
  - Rule: EMA factor `α = 1 − exp(−interval/tau)`; `turn = k_turn·(dna_right − dna_left)`; `boost = boost_max·tanh(k_gf·gf)`; `speed = base·(1 + boost)`; `left = speed + turn/2`, `right = speed − turn/2`; clip to `[drive_min, drive_max]`.
  - Biology of the sign: DNa02 activity on one side turns the fly to that side; in `HybridTurningController` the side with the smaller drive is the inside of the turn. Hence right-side DNa activity ⇒ right drive smaller.

- [ ] **Step 1: Write failing tests**

```python
def test_silent_brain_walks_straight_at_base():
    m = MotorMapper(MotorConfig())
    assert m.update(DNRates(0, 0, 0)) == pytest.approx([0.7, 0.7])

def test_right_dna_activity_turns_right():
    m = MotorMapper(MotorConfig())
    for _ in range(20): d = m.update(DNRates(0, 60, 0))
    assert d[1] < d[0]

def test_giant_fiber_boosts_speed_and_saturates():
    m = MotorMapper(MotorConfig())
    for _ in range(50): d = m.update(DNRates(0, 0, 1e6))
    assert d == pytest.approx([0.7 * 1.8, 0.7 * 1.8], rel=1e-3)

def test_drives_are_clipped():
    m = MotorMapper(MotorConfig(k_turn=1.0))
    for _ in range(50): d = m.update(DNRates(0, 1000, 0))
    assert d[0] == 1.5 and d[1] == 0.0

def test_ema_first_step():
    m = MotorMapper(MotorConfig())
    m.update(DNRates(0, 100, 0))
    assert m.smoothed.dna_right == pytest.approx(100 * (1 - math.exp(-20 / 50)))
```

- [ ] **Step 2: Run** `uv run pytest tests/test_motor.py -q` → FAIL.
- [ ] **Step 3: Implement** `flybrain/motor.py`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: add descending-neuron to drive mapping`

---

### Task 7: Body wrapper (FlyGym)

**Files:**
- Create: `flybrain/body.py`, `tests/test_body.py`

**Interfaces:**
- Consumes: `FlyStart` (Task 2).
- Produces:
  - `@dataclass class BodyState`: `thorax: np.ndarray` (3,), `head: np.ndarray`, `eye_left: np.ndarray`, `eye_right: np.ndarray`, `forward: np.ndarray` (unit, ground plane), `flipped: bool`, `finite: bool`
  - `class FlyBody`:
    - `__init__(self, start: FlyStart, seed: int)` builds `Fly(spawn_pos=(x, y, 0.2), spawn_orientation=(0, 0, heading_rad), enable_adhesion=True, detect_flip=True, contact_sensor_placements=<Tibia, Tarsus1–5 for all six legs>)` on `FlatTerrain()` with `HybridTurningController(..., cameras=[], timestep=1e-4, seed=seed)` and calls `reset(seed=seed)`.
    - `step(self, drive: np.ndarray, n_steps: int) -> BodyState`
    - `state(self) -> BodyState` (eye/head positions from bodies `LEye`, `REye`, `Head` via `physics.bind`; `forward` = thorax x-axis from `xmat`, z zeroed, normalised; `flipped` from the controller's `terminated` flag)
    - `part_names: list[str]` = names of the 69 mesh geoms, fixed order
    - `part_poses(self) -> np.ndarray` float32 `(69, 7)`: geom world position + quaternion `(w, x, y, z)` from `physics.bind(geoms).xpos/.xmat` (convert with `mujoco.mju_mat2Quat`). Geom (not body) poses, because Plan 2 exports the compiled meshes in geom frame.
  - No rendering; no camera; no GL needed.

- [ ] **Step 1: Write failing tests** (each run ≤ 0.1 s simulated to keep CI fast)

```python
def test_walks_forward_along_heading():
    b = FlyBody(FlyStart(pos=(0, 0), heading_deg=90), seed=0)
    s0 = b.state(); s1 = b.step(np.array([1.0, 1.0]), 1000)
    disp = s1.thorax[:2] - s0.thorax[:2]
    assert np.dot(disp, [0, 1]) > 0.3 and abs(disp[0]) < np.dot(disp, [0, 1])
    assert np.allclose(s0.forward[:2], [0, 1], atol=0.1)

def test_smaller_left_drive_turns_left():
    b = FlyBody(FlyStart(pos=(0, 0), heading_deg=0), seed=0)
    b.step(np.array([1.0, 1.0]), 300)
    s = b.step(np.array([0.3, 1.2]), 1000)
    assert s.forward[1] > 0.05                       # yawed toward +y (left)

def test_part_poses_shape_and_unit_quaternions():
    b = FlyBody(FlyStart(pos=(0, 0), heading_deg=0), seed=0)
    p = b.part_poses()
    assert p.shape == (69, 7) and p.dtype == np.float32 and len(b.part_names) == 69
    assert np.allclose(np.linalg.norm(p[:, 3:], axis=1), 1, atol=1e-4)
    assert b.state().finite and not b.state().flipped
```

- [ ] **Step 2: Run** `uv run pytest tests/test_body.py -q` → FAIL.
- [ ] **Step 3: Implement** `flybrain/body.py`. If the turn test shows the opposite sign, stop and report: Task 6's sign convention depends on it.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: add FlyGym body wrapper with geom poses`

---

### Task 8: Recording format

**Files:**
- Create: `flybrain/recording.py`, `tests/test_recording.py`, `docs/recording-format.md`

**Interfaces:**
- Produces:
  - `FORMAT_VERSION = 1`
  - `class RecordingWriter`:
    - `__init__(self, out_dir: Path, meta: dict, part_names: list[str])` (creates dir; `meta` holds scene, seed, config hash, package version, fps=50)
    - `append(self, poses: np.ndarray, spikes: np.ndarray, signals: dict[str, float | list[float]]) -> None`
    - `close(self, status: Literal["complete", "aborted"], reason: str | None = None, warnings: list[str] = []) -> None` writes all files
  - Files per spec §5: `meta.json` (`format_version`, `n_frames`, `n_parts`, `part_names`, `status`, `reason`, `warnings`, …), `body.bin` (float32 `n_frames × n_parts × 7`, little-endian), `spikes.bin` (uint32 `n_frames+1` offsets, then uint32 indices), `signals.json` (dict of per-frame lists).
  - `@dataclass class Recording`: `meta`, `poses` (np.ndarray), `spike_offsets`, `spike_indices`, `signals`; `frame_spikes(i) -> np.ndarray`
  - `def read_recording(path: Path) -> Recording` raises `ValueError("unsupported format_version …")` for other versions.
  - JSON written with sorted keys and fixed float formatting so byte-identity holds.
  - `docs/recording-format.md`: byte layout; Plan 2's TypeScript reader is written from it.

- [ ] **Step 1: Write failing tests**

```python
def test_round_trip(tmp_path):
    w = RecordingWriter(tmp_path, {"seed": 1}, ["a", "b"])
    for i in range(3):
        w.append(np.full((2, 7), i, np.float32), np.array([i, i + 10], np.uint32), {"drive_left": 0.5})
    w.close("complete")
    r = read_recording(tmp_path)
    assert r.meta["n_frames"] == 3 and r.poses.shape == (3, 2, 7)
    assert list(r.frame_spikes(2)) == [2, 12] and r.signals["drive_left"] == [0.5] * 3

def test_aborted_partial_recording_readable(tmp_path):
    w = RecordingWriter(tmp_path, {}, ["a"]); w.append(np.zeros((1, 7), np.float32), np.array([], np.uint32), {})
    w.close("aborted", reason="flipped")
    r = read_recording(tmp_path)
    assert r.meta["status"] == "aborted" and r.meta["reason"] == "flipped" and r.meta["n_frames"] == 1

def test_rejects_unknown_version(tmp_path):
    ...write a valid recording, set meta["format_version"] = 99...
    with pytest.raises(ValueError, match="format_version"):
        read_recording(tmp_path)
```

- [ ] **Step 2: Run** `uv run pytest tests/test_recording.py -q` → FAIL.
- [ ] **Step 3: Implement** `flybrain/recording.py` and write `docs/recording-format.md`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: add recording format writer and reader`

---

### Task 9: Closed loop

**Files:**
- Create: `flybrain/loop.py`, `tests/test_loop.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `class Controller(Protocol)`: `def drive(self, t_s: float, body: BodyState) -> tuple[np.ndarray, np.ndarray, dict]` returns (drive (2,), spiking neuron indices, signals for this frame)
  - `class ConstantController`: `__init__(self, drive: tuple[float, float])`; no spikes; signals `{"drive_left", "drive_right"}`
  - `class BrainController`: `__init__(self, brain: LIFBrain, encoder: LoomingEncoder, mapper: MotorMapper, connectome: Connectome)`; inputs = `LPLC2`+`LC4` per side; reads `DNa01`, `DNa02`, `DNp01` per side; per call: rates from encoder → `brain.step(200, …)` → DN rates (count / 0.02 s) → mapper. Signals: `threat_x/y/z`, `theta_left_deg`, `theta_right_deg`, `input_left_hz`, `input_right_hz`, `dna_left_hz`, `dna_right_hz`, `gf_hz`, `drive_left`, `drive_right`, `active_neurons`.
  - `@dataclass class RunResult`: `status`, `reason`, `n_frames`, `wall_s`, `warnings`
  - `def run_scene(scene: Scene, config: Config, controller: Controller, out_dir: Path, progress: Callable[[float], None] | None = None) -> RunResult`
    - builds `FlyBody(scene.fly, scene.seed)`; loop `n_frames = floor(duration_s / 0.02)` times: `controller.drive` → `body.step(drive, 200)` → `writer.append(body.part_poses(), spikes, signals)`; frame 0 is the state after the first interval.
    - aborts (status `aborted`, partial recording kept) with reason `flipped`, `non_finite`, or `out_of_arena` (thorax distance from origin > `arena_radius_mm`).
    - adds warning `brain_runaway` once if any frame's `active_neurons > runaway_active_neurons`.
    - `progress(frame / n_frames)` after each frame.
  - `def make_brain_controller(scene, config, connectome, device="cpu") -> BrainController`

- [ ] **Step 1: Write failing tests** (add fixture `fixture_connectome` to `conftest.py`: ~20 neurons with cell types `LPLC2`, `LC4`, `DNa01`, `DNa02`, `DNp01` on both sides, wired input → DN with strong excitatory edges, so `BrainController` can be built without real data; `scene_with(**kw)` and `LOUD` are local helpers deriving from `scenes/examples/loom_left.json`. Abort checks run after the frame is appended, so an aborted run has ≥ 1 frame.)

```python
SHORT = scene_with(duration_s=0.2)

def test_frame_count_floors_duration(tmp_path):
    r = run_scene(scene_with(duration_s=0.21), load_config(), ConstantController((1, 1)), tmp_path)
    assert r.status == "complete" and r.n_frames == 10

def test_deterministic_recording(tmp_path, fixture_connectome):
    for d in ("a", "b"):
        ctrl = make_brain_controller(SHORT, load_config(), fixture_connectome)
        run_scene(SHORT, load_config(), ctrl, tmp_path / d)
    for f in ("meta.json", "body.bin", "spikes.bin", "signals.json"):
        assert (tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes()

def test_out_of_arena_aborts_with_partial_recording(tmp_path):
    cfg = load_config(); cfg.run.arena_radius_mm = 0.05
    r = run_scene(SHORT, cfg, ConstantController((1.2, 1.2)), tmp_path)
    assert r.status == "aborted" and r.reason == "out_of_arena"
    assert read_recording(tmp_path).meta["n_frames"] == r.n_frames >= 1

def test_runaway_warning(tmp_path, fixture_connectome):
    cfg = load_config(); cfg.run.runaway_active_neurons = 0
    ctrl = make_brain_controller(LOUD, cfg, fixture_connectome)   # LOUD: fast threat at the fly
    assert "brain_runaway" in run_scene(LOUD, cfg, ctrl, tmp_path).warnings

def test_progress_reaches_one(tmp_path):
    seen = []
    run_scene(SHORT, load_config(), ConstantController((1, 1)), tmp_path, progress=seen.append)
    assert seen[-1] == pytest.approx(1.0) and seen == sorted(seen)
```

`meta.json` must not contain wall-clock time (it would break determinism). `wall_s` lives in `RunResult` only.

- [ ] **Step 2: Run** `uv run pytest tests/test_loop.py -q` → FAIL.
- [ ] **Step 3: Implement** `flybrain/loop.py`.
- [ ] **Step 4: Run** → PASS; full suite `uv run pytest -m "not slow" -q` → PASS.
- [ ] **Step 5: Commit** `feat: add brain-body closed loop`

---

### Task 10: CLI and first end-to-end run

**Files:**
- Create: `flybrain/cli.py`, `tests/test_cli.py`, `scenes/examples/loom_right.json`, `scenes/examples/no_threat.json`
- Modify: `README.md` (install, `download-data`, `run` usage, data licence note)

**Interfaces:**
- Produces (Typer app `app`):
  - `flybrain download-data [--data-dir data]`
  - `flybrain run SCENE --out DIR [--config PATH] [--data-dir data] [--device cpu] [--no-brain]` (`--no-brain` ⇒ `ConstantController((base_drive, base_drive))`, no data needed). Prints status, frames, wall time, and wall seconds per simulated second. Exit code 0 for `complete`, 2 for `aborted`, 1 for errors (invalid scene, `DataError`), with the message on stderr.

- [ ] **Step 1: Write failing tests** with `typer.testing.CliRunner`:

```python
def test_run_no_brain(tmp_path):
    r = runner.invoke(app, ["run", "scenes/examples/no_threat.json", "--out", str(tmp_path), "--no-brain"])
    assert r.exit_code == 0 and read_recording(tmp_path).meta["status"] == "complete"

def test_invalid_scene_exit_1(tmp_path):
    bad = tmp_path / "bad.json"; bad.write_text('{"duration_s": 0}')
    r = runner.invoke(app, ["run", str(bad), "--out", str(tmp_path / "o"), "--no-brain"])
    assert r.exit_code == 1 and "duration_s" in r.output

def test_missing_data_exit_1(tmp_path):
    r = runner.invoke(app, ["run", "scenes/examples/loom_left.json", "--out", str(tmp_path), "--data-dir", str(tmp_path)])
    assert r.exit_code == 1 and "download-data" in r.output
```

`no_threat.json` is 0.2 s long (CI speed); its threat path stays far away and slow.

- [ ] **Step 2: Run** `uv run pytest tests/test_cli.py -q` → FAIL.
- [ ] **Step 3: Implement** `flybrain/cli.py`; add `loom_right.json` (mirror of `loom_left`); update README.
- [ ] **Step 4: Run** → PASS; full suite → PASS.
- [ ] **Step 5: End-to-end on real data (manual, VPS)**

Run: `uv run flybrain run scenes/examples/loom_left.json --out out/loom_left` and the same for `loom_right`.
Expected: status `complete`, 150 frames each. In `signals.json`: `gf_hz` peaks well above 0 during the approach; `dna_right_hz > dna_left_hz` for `loom_left` and the reverse for `loom_right`; the fly's final heading turned away from the threat side (compare `forward` direction from first/last thorax poses). Record wall time per simulated second in the commit body. If the turn is absent or reversed, do not tweak constants here; note it for calibration in Plan 3.

- [ ] **Step 6: Commit** `feat: add CLI; first end-to-end looming run`

---

## Done when

- `uv run pytest -m "not slow"` green locally and in CI; `uv run pytest -m slow` green on the VPS with data.
- `flybrain run --no-brain` produces a recording that Plan 2 can replay.
- `loom_left` / `loom_right` end-to-end runs completed, with observed behaviour and timing noted.
