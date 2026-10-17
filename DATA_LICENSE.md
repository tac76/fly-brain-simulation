# Data licence

The code in this repository is MIT-licensed (see `LICENSE`). The connectome data and files
derived from it are not.

## FlyWire connectome (CC BY-NC 4.0)

The brain model uses the FlyWire FAFB v783 connectome. It is downloaded by
`flybrain download-data` and is **not** part of this repository:

- neuron list and signed connectivity from the Shiu et al. 2024 model repository
  (github.com/philshiu/Drosophila_brain_model),
- cell-type annotations from github.com/flyconnectome/flywire_annotations.

FlyWire data is licensed under
[Creative Commons Attribution-NonCommercial 4.0](https://creativecommons.org/licenses/by-nc/4.0/).

These files in this repository are derived from it and are released under the same licence
(CC BY-NC 4.0, attribution below, non-commercial use only):

- `viewer/public/assets/brain_points.bin`, `viewer/public/assets/brain_points.json`
- the recordings in `viewer/public/gallery/` (they contain neuron indices and spike times)

### Attribution

- Dorkenwald, S. et al. *Neuronal wiring diagram of an adult brain.* Nature 634 (2024).
- Schlegel, P. et al. *Whole-brain annotation and multi-connectome cell typing of Drosophila.*
  Nature 634 (2024).
- FlyWire: https://flywire.ai
