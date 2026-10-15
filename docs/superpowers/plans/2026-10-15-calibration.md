# Calibration Implementation Plan (Plan 1b)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (chosen: native). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Choose the stimulus and motor constants so the brain-driven escape is clearly visible (turn away from the threat, speed-up), measured against a no-brain baseline, and document the choice.

**Architecture:** A `metrics` module compares a brain run with a no-brain run of the same scene. A `scripts/calibrate.py` grid search runs config variants over a fixed set of calibration scenes in parallel and writes a results table. The chosen values go into `config/default.yaml`, with the reasoning in `docs/calibration.md`. Pulled forward from Plan 3 (spec §4.3) because the uncalibrated escape is too small to show.

**Tech Stack:** as Plan 1; `multiprocessing` for parallel runs.

**Spec:** `docs/superpowers/specs/2026-10-14-fly-brain-simulation-design.md` (§4.1–4.3)

## Findings this plan builds on (measured 2026-10-14, merged `main` ae47b66)

- Closed-loop runs of the example scenes: input peaks at ~55–60 Hz for a frame or two, mostly 10–25 Hz; DNa01/DNa02 fire 0–2 spikes per run; turn vs no-brain baseline 0–2°. The no-brain gait alone drifts ~3° over 3 s.
- Brain only, constant input to one eye's LPLC2+LC4: contralateral DNa01+DNa02 sum 40–60 Hz for any input from 50 to 250 Hz (fast saturation), ipsilateral 0 Hz; giant fiber grows 120 to 240 Hz. Input to both eyes (150/75 Hz) cuts the contralateral DNa to 13 Hz.
- Conclusion: the bottleneck is the encoder (rates too low for most of the approach) and slow example threats (r/v = 100 ms; looming experiments use roughly 10–80 ms).

## Global Constraints

- Plan 1 constraints apply (units, timesteps, determinism, data handling, commits as `tac76`).
- Brain model parameters stay untouched. Only `stimulus.*` and `motor.*` in `config/default.yaml` are tuned.
- Every turn is reported relative to the no-brain run of the same scene and seed.
- Acceptance (with the chosen config, on the calibration scenes):
  - `loom_left_fast`: turn ≤ −20° (toward the fly's right, away from the threat) vs baseline; giant-fiber peak > 100 Hz; status `complete`.
  - `loom_right_fast`: mirror, turn ≥ +20°.
  - `slow_far`: |turn| < 5° vs baseline, input stays 0.
  - `loom_front`: path length ≥ 10 % longer than baseline (speed-up); |turn| reported, no threshold.
- If no grid point meets acceptance, do not widen the mapping beyond the spec's formulas: report the best point and the gap.

## Review Focus

1. Calibration scenes whose threat starts inside the arena edge or hits the fly at t = 0 → scene validation rejects or the run still completes → test in Task 2 (all calibration scenes load and validate).
2. A brain run that aborts (flip, out of arena) while its baseline completes → metrics computed over the common frame range, row marked aborted → test in Task 1.
3. Heading wrap-around at ±180° → turn computed with angle unwrapping → test in Task 1.

---

### Task 1: Paired-baseline metrics

**Files:** Create `flybrain/metrics.py`, `tests/test_metrics.py`

**Interfaces:**
- Consumes: `Recording` (Plan 1, Task 8).
- Produces:
  - `def walk_heading_deg(rec: Recording, start: int, end: int) -> float`: direction of thorax displacement between frames `start` and `end` (atan2 of Δy, Δx), degrees.
  - `@dataclass class EscapeMetrics`: `turn_deg: float` (brain minus baseline, wrapped to (−180, 180]), `path_ratio: float` (brain path length / baseline path length over the common frames), `gf_peak_hz: float`, `input_peak_hz: float`, `status: str`
  - `def escape_metrics(brain: Recording, baseline: Recording) -> EscapeMetrics`: common frame range `n = min(n_brain, n_baseline)`; turn = heading over frames `[n//2, n−1]` brain minus baseline (late window, after the threat has passed); `gf_peak_hz`/`input_peak_hz` from brain signals (0 if absent); status from brain meta.

- [ ] **Step 1: Failing tests** with synthetic recordings built by `RecordingWriter` (thorax part only):
  - straight +x brain vs straight +x baseline → `turn_deg == 0`, `path_ratio == 1`
  - brain bending to −y in the second half → `turn_deg < 0`
  - headings 179° vs −179° → `turn_deg == pytest.approx(-2)` (wrap)
  - brain aborted after 6 of 10 frames → uses 6 frames, `status == "aborted"`
- [ ] **Step 2:** run, see FAIL. **Step 3:** implement. **Step 4:** PASS. **Step 5:** commit `feat: add paired-baseline escape metrics`.

### Task 2: Calibration scenes and grid script

**Files:** Create `scenes/calibration/{loom_left_fast,loom_right_fast,loom_front,slow_far}.json`, `scripts/calibrate.py`, `tests/test_calibration_scenes.py`

**Interfaces:**
- Scenes (all `duration_s: 2`, `seed: 1`, fly at origin heading 0, threat diameter 8 mm, i.e. r = 4 mm):
  - `loom_left_fast`: path `[[0, 30, 6], [0, 2, 2]]`, speed 100 mm/s (r/v = 40 ms)
  - `loom_right_fast`: mirror (`y` negated)
  - `loom_front`: path `[[30, 0, 6], [3, 0, 2]]`, speed 100 mm/s
  - `slow_far`: path `[[40, 30, 15], [35, 30, 15]]`, speed 2 mm/s
- `scripts/calibrate.py --grid <name> --out out/calibration [--workers 4]`:
  - grid `default`: `stimulus.theta_dot_0_deg_s ∈ {5, 20}`, `stimulus.theta_dot_sat_deg_s ∈ {100, 200, 300}`, `motor.k_turn ∈ {0.01, 0.02, 0.04}` (18 configs)
  - one no-brain baseline per scene (shared by all configs), then every (config, scene) brain run, parallel via `multiprocessing.Pool` (each worker loads the connectome once)
  - writes `results.csv` (config values, scene, all `EscapeMetrics` fields, wall time) and `results.md` (one row per config: turn left/right/front/slow, path ratio front, pass/fail per acceptance line)
  - deterministic ordering of rows

- [ ] **Step 1: Failing test** `test_calibration_scenes_valid`: every file in `scenes/calibration/` loads and passes `validate_against(load_config())`; `loom_right_fast` is the y-mirror of `loom_left_fast`.
- [ ] **Step 2–4:** add scenes, RED→GREEN. Script is exercised by Task 3 (no unit test; it is a thin driver over tested modules).
- [ ] **Step 5:** commit `feat: add calibration scenes and grid search script`.

### Task 3: Run, choose, document

**Files:** Modify `config/default.yaml`, `scenes/examples/loom_left.json`, `scenes/examples/loom_right.json`, `README.md`; Create `docs/calibration.md`

- [ ] **Step 1:** `uv run python scripts/calibrate.py --grid default --out out/calibration --workers 4`. Expected: 18 × 4 brain runs + 4 baselines, `results.md` written.
- [ ] **Step 2:** pick the config that meets acceptance with the smallest `k_turn`, then the largest `theta_dot_0` (fewest false reactions). If none passes, stop here and report the best row and the gap (no formula changes).
- [ ] **Step 3:** write the values into `config/default.yaml` (remove "initial guess" comments for tuned keys); set example scenes to the fast variants' speed (100 mm/s) so the README examples show the escape.
- [ ] **Step 4:** `docs/calibration.md`: method (paired baseline, late-window heading), the brain-only findings above, results table (copy of `results.md`), chosen values and why, known limits. README: replace "escape is still small" with the measured numbers and link `docs/calibration.md`.
- [ ] **Step 5:** full suite green; commit `feat: calibrate stimulus and motor constants`.

## Done when

- Acceptance lines met (or a documented gap), `docs/calibration.md` committed, suite green, merged to `main`.
