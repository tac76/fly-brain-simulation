# Brain points format

Written by `scripts/export_brain_points.py` into `viewer/public/assets/`. Derived from FlyWire FAFB
v783 (CC BY-NC 4.0).

## `brain_points.bin`

Little-endian. `n` = number of neurons in the model (138 639), in connectome index order (rows of
`Completeness_783.csv`, the same index as in a recording's `spikes.bin`).

1. `float32[n][3]`: position in micrometres. FlyWire `pos_x/y/z` × (0.004, 0.004, 0.04),
   y and z negated (so +y is dorsal and the brain is upright with +z toward the viewer), centred on
   the mean of all annotated neurons. Neurons without annotation sit at the origin.
2. `uint8[n]`: group id, an index into `groups` in the JSON file.

## `brain_points.json`

| Key | Meaning |
|---|---|
| `n` | number of neurons |
| `groups` | group names: `unknown`, the FlyWire super classes, then the highlighted groups |
| `colors` | base colour per group (hex) |
| `highlight` | groups the viewer labels: `LPLC2_L/R`, `LC4_L/R` (looming input), `DNp01_L/R` (giant fiber), `DNa_L/R` (steering, DNa01 + DNa02) |
| `bounds_um` | min and max position |
| `license` | data licence note |

A neuron's group is its highlighted group if it has one, otherwise its super class.
