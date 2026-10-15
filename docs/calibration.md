# Calibration

How the hand-built constants between the brain model and the world were chosen.
The brain model itself (FlyWire wiring, Shiu et al. 2024 parameters) is not tuned.

Date: 2026-10-15. Code: `scripts/calibrate.py`, scenes: `scenes/calibration/`.

## What is tuned

| Constant | Role | Before | After |
|---|---|---|---|
| `stimulus.theta_dot_0_deg_s` | expansion rate where eye input starts | 20 | **5** |
| `stimulus.theta_dot_sat_deg_s` | expansion rate where eye input saturates at 150 Hz | 300 | **300** |
| `motor.k_turn` | drive difference per Hz of right-minus-left DNa01+DNa02 | 0.01 | **0.02** |

Not tuned (initial choices): `theta_min_deg`, `overlap_deg`, `r_max_hz` (150 Hz, the model's
default activation rate), `base_drive`, `tau_ms`, `k_gf`, `boost_max`, drive limits.

## Why the first version barely escaped

- Example threats were slow: 8 mm sphere at 40 mm/s, i.e. a size-to-speed ratio r/v = 100 ms.
  Looming experiments with flies use roughly 10–80 ms. The eye input therefore stayed at
  10–25 Hz for most of the approach and peaked at ~55–60 Hz for a frame or two.
- The brain needs sustained input. With constant input to one eye's LPLC2+LC4 neurons
  (brain only, no body), the contralateral DNa01+DNa02 fire 40–60 Hz for any input from 50 to
  250 Hz, the ipsilateral ones stay silent, and the giant fiber rises from 120 to 240 Hz.
  Input to both eyes (150/75 Hz) cuts the contralateral DNa response to 13 Hz.
- Result before calibration: 0–2 DNa spikes per run and a turn of 0–2° relative to a no-brain
  run.

## Method

- Four 2 s scenes, fly at the origin facing +x, threat 8 mm diameter:
  `loom_left_fast` / `loom_right_fast` (from the side, 100 mm/s, r/v = 40 ms), `loom_front`
  (head-on, 100 mm/s), `slow_far` (far away, 2 mm/s; should cause nothing).
- Every brain run is compared with a no-brain run of the same scene and seed. The gait alone
  drifts by a few degrees, so only the difference counts.
- Turn = change in walking direction (thorax displacement over the second half of the run),
  brain minus baseline; + = left. Path ratio = path length brain / baseline.
- Grid: `theta_dot_0` ∈ {5, 20}, `theta_dot_sat` ∈ {100, 200, 300}, `k_turn` ∈ {0.01, 0.02, 0.04}
  (18 configs × 4 scenes, seed 1).
- Acceptance: turn away ≥ 20° on both sides, giant fiber > 100 Hz, `slow_far` |turn| < 5° with
  zero input, `loom_front` path ratio ≥ 1.10, no aborted run.
- Selection rule (fixed before the run): among passing configs, smallest `k_turn`, then largest
  `theta_dot_0`.

## Results (seed 1)

| stimulus.theta_dot_0_deg_s | stimulus.theta_dot_sat_deg_s | motor.k_turn | turn L | turn R | turn front | turn slow | path front | GF L/R | pass |
|---|---|---|---|---|---|---|---|---|---|
| 5 | 100 | 0.01 | -22.3 | +38.3 | +15.5 | +0.0 | 1.10 | 250/250 | no |
| 5 | 100 | 0.02 | -37.9 | +66.8 | +32.9 | +0.0 | 1.10 | 250/225 | no |
| 5 | 100 | 0.04 | -58.8 | +84.9 | +35.0 | +0.0 | 1.11 | 250/225 | yes |
| 5 | 200 | 0.01 | -31.4 | +43.2 | +11.6 | +0.0 | 1.09 | 225/225 | no |
| 5 | 200 | 0.02 | -47.7 | +60.6 | +21.8 | +0.0 | 1.08 | 225/250 | no |
| 5 | 200 | 0.04 | -50.9 | +88.3 | +33.8 | +0.0 | 1.10 | 250/225 | yes |
| 5 | 300 | 0.01 | -10.8 | +34.2 | +10.0 | +0.0 | 1.10 | 250/225 | no |
| 5 | 300 | 0.02 | -36.0 | +56.8 | +21.3 | +0.0 | 1.10 | 250/225 | yes |
| 5 | 300 | 0.04 | -62.3 | +86.8 | +24.2 | +0.0 | 1.10 | 250/225 | no |
| 20 | 100 | 0.01 | -15.7 | +38.0 | +20.3 | +0.0 | 1.11 | 225/225 | no |
| 20 | 100 | 0.02 | -40.2 | +73.5 | +3.7 | +0.0 | 1.10 | 225/225 | no |
| 20 | 100 | 0.04 | -52.5 | +95.2 | +33.5 | +0.0 | 1.08 | 250/250 | no |
| 20 | 200 | 0.01 | -14.5 | +37.3 | +4.0 | +0.0 | 1.10 | 225/250 | no |
| 20 | 200 | 0.02 | -50.8 | +59.0 | +0.9 | +0.0 | 1.09 | 250/225 | no |
| 20 | 200 | 0.04 | -53.6 | +81.4 | -5.1 | +0.0 | 1.12 | 200/225 | yes |
| 20 | 300 | 0.01 | -15.0 | +31.2 | +2.6 | +0.0 | 1.09 | 250/225 | no |
| 20 | 300 | 0.02 | -28.6 | +44.4 | +2.6 | +0.0 | 1.08 | 225/250 | no |
| 20 | 300 | 0.04 | -45.9 | +97.2 | -4.9 | +0.0 | 1.09 | 200/250 | no |

Selected: `theta_dot_0 = 5`, `theta_dot_sat = 300`, `k_turn = 0.02`.

Robustness check of the selected config on seeds 2 and 3:

| Seed | turn L | turn R | turn front | turn slow | path front |
|---|---|---|---|---|---|
| 2 | −39.7 | +53.9 | −25.7 | 0.0 | 1.09 |
| 3 | −44.8 | +56.9 | +3.6 | 0.0 | 1.10 |

## Findings and limits

- **The escape direction is correct and robust:** threat from the left turns the fly right
  (−36° to −45°), from the right turns it left (+54° to +57°), across three seeds. A slow,
  distant object causes no input and no turn.
- **Left/right asymmetry:** turns to the left are ~1.5× larger. The constants are symmetric,
  so this comes from the wiring itself (left and right DNa01/DNa02 do not receive identical
  input in the connectome).
- **Head-on threats:** the turn direction varies with the seed (−26° to +21°). Both eyes get
  equal input and inhibit each other's steering; small random differences decide the side.
- **Speed-up is modest:** 8–10 % longer path than the baseline. The acceptance line
  (≥ 1.10) is met only at seed 1 and is borderline on the others. The giant fiber fires
  strongly but briefly, and its boost decays with the 50 ms smoothing. `k_gf`, `boost_max`
  and `tau_ms` were not part of this grid; a follow-up could tune them.
- **Real flies jump.** A looming threat usually triggers a giant-fiber takeoff. This fly only
  walks, so the escape shows as turning away and walking faster.
