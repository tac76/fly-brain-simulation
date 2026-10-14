# Recording format (version 1)

One folder per simulation run. All binary data is little-endian. Frame rate: 50 fps (one frame
per 20 ms brain/body exchange). Frame 0 is the state after the first 20 ms interval.

## `meta.json`

UTF-8 JSON object, keys sorted. Always present:

| Key | Type | Meaning |
|---|---|---|
| `format_version` | int | `1` |
| `fps` | int | `50` |
| `n_frames` | int | number of frames in the files below |
| `n_parts` | int | number of body parts (69 mesh geoms of NeuroMechFly) |
| `part_names` | string[] | body-part names, in the order used by `body.bin` |
| `status` | `"complete"` \| `"aborted"` | |
| `reason` | string \| null | why an aborted run stopped: `flipped`, `non_finite`, `out_of_arena` |
| `warnings` | string[] | e.g. `brain_runaway` |

Written by the simulation loop in addition: `scene`, `seed`, `config_hash`, `package_version`.

## `body.bin`

`float32[n_frames][n_parts][7]`: world position `x, y, z` (mm, z up) followed by the orientation
quaternion `w, x, y, z` of each body part's mesh frame (MuJoCo geom frame, i.e. the compiled mesh
frame). Size: `n_frames * n_parts * 28` bytes.

## `spikes.bin`

`uint32[n_frames + 1]` offsets, then `uint32[offsets[n_frames]]` neuron indices.
Neurons that spiked during frame `i` are `indices[offsets[i] : offsets[i+1]]`.
A neuron index is the row number in FlyWire `Completeness_783.csv` (0 to 138638).

## `signals.json`

UTF-8 JSON object `{name: [value per frame]}`; values are numbers (rounded to 6 decimals) or
lists of numbers. Brain runs write: `threat_x`, `threat_y`, `threat_z`, `theta_left_deg`,
`theta_right_deg`, `input_left_hz`, `input_right_hz`, `dna_left_hz`, `dna_right_hz`, `gf_hz`,
`drive_left`, `drive_right`, `active_neurons`.
