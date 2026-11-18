# Mono Spiral 35x35 reference geometry

Run the unit tests from this directory:

```bash
python -m unittest -v
```

The reference winding is a 13-turn continuous square spiral with 350 mm
outer side, 1.20 mm centre-to-centre pitch and 0.60 mm wire. The geometry
model includes the 12 radial inter-turn transitions. It calculates the
idealized copper path length, 20 C copper resistance estimate, and a
magnetostatic Biot-Savart field estimate.

Generate a two-dimensional field map at 40, 80 and 120 mm above the coil:

```bash
python run_mono_spiral_field_map.py
```

This writes `mono_spiral_magnetostatic_field_map.csv` (1,323 sample points,
21 x 21 per height). The field is normalized to 1 A so results scale linearly
with current within this magnetostatic model. The CSV is a numerical reference,
not a measured field map.

## Model boundaries

- The winding is treated as a thin filament in the z=0 plane.
- External cable leads, wire insulation, finite conductor cross-section,
  temperature rise and nearby structures are not represented.
- The field map is magnetostatic. It does not simulate the PI switching
  waveform, target eddy currents, soil response, receiver loading, clamp
  recovery or analogue front end.
- No detection depth, metal classification, soil performance or hardware
  safety claim follows from these calculations.

## Transient and conducting-target models

- `mono_spiral_transient.py`: first-order coupled primary/target RL model.
- `mono_spiral_disk.py`: multi-ring conducting-disk surrogate with mutual
  inductance between the square winding and concentric eddy-current loops.
- `test_mono_spiral_disk.py`: target-surrogate regression tests.
- `run_disk_convergence.py`: angular and radial sensitivity sweeps.
- `run_coil_inductance_sensitivity.py`: compares the transient response across the two provisional planar-spiral inductance estimates and their midpoint.

The disk model is a reduced-order axisymmetric approximation, not 3-D FEM.
It uses equal-area annuli and currently rejects more than 8 target rings
because higher refinement produced a numerically unreliable response in the
present thin-ring approximation. Target values in tests are synthetic
fixtures, not selected field targets. The previous radial sweep changed by
about 0.676% from 7 to 8 rings, so radial convergence is not established.
Time-step sensitivity results support numerical stability only for the
documented synthetic fixtures. See
`docs/science/MONO_SPIRAL_DISK_SURROGATE_CONVERGENCE_AR.md` and
`docs/science/MONO_SPIRAL_CONTINUOUS_PATH_AUDIT_AR.md`.

The disk transient model's default coil inductance (175.8 uH) is a provisional
simulation input, not a measured or independently validated property. Its
1.0641 ohm winding resistance is a 20 C geometry-based copper estimate.
Likewise, the 12 V / 200 us pulse and 20 ohm clamp are software fixtures,
not approved hardware specifications. Do not use these defaults for power
stage selection or safety calculations; see the Arabic science audit.

The geometry model also exposes two independent first-order planar-spiral
inductance estimates from Mohan et al. (current-sheet and modified Wheeler).
For the current 350 mm / 13-turn geometry they differ by roughly 15%, so
175.8 uH remains a provisional input rather than a validated coil property.
The published expressions were benchmarked on much smaller planar inductors;
a Greenhouse/path-specific calculation and eventual LCR measurement remain
necessary before power-stage design.
