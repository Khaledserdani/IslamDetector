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
- `greenhouse_inductance.py`: independent path-specific quasi-static partial-inductance estimator. It merges the 12 collinear spiral connectors, sums finite round-wire self terms and signed finite-length mutual terms averaged over both circular cross-sections.
- `test_greenhouse_inductance.py`: reference, reciprocity, sign, geometry, quadrature and independent Neumann-kernel tests for the estimator.
- `run_greenhouse_inductance.py`: evaluates 2x8, 4x16 and 8x32 cross-section quadrature orders and enforces a 0.1% final-step convergence threshold.
- `run_disk_positive_definite_diagnostics.py`: checks whether known rejected disk fixtures recover when ring polygon resolution increases from 48 to 384.
- `run_disk_radial_basis_diagnostics.py`: checks Cholesky stability as the number of annular target basis loops changes from 3 to 8.

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

## Greenhouse path-specific inductance estimate

The production reference implementation now exists in `greenhouse_inductance.py`. For the nominal 13-turn, 350 mm square, 1.20 mm pitch, 0.60 mm round-wire path it merges the 12 radial connectors into 52 physical straight sections while preserving the 17.4512 m copper path. The reference 4x16 cross-section quadrature gives a diagnostic partial quasi-static inductance of approximately 172.067221 µH: self terms 24.307039 µH, positive mutual terms +84.474332 µH and negative mutual terms -10.594241 µH before the required factor of two. This reproduces the independent numerical audit and is covered by unit tests.

This number is not a measured terminal inductance and is not a final PI-frequency effective inductance. It assumes uniform DC current density, ideal sharp corners, and excludes external leads/return path, skin effect, proximity effect and nearby conductive structures. The Greenhouse runner tests cross-section quadrature convergence; a physical LCR measurement with documented fixture/lead geometry remains required before changing the transient model's provisional Coil default or selecting power components.

The 2026-11-19 diagnostics found that increasing polygon resolution from 48 to 384 did not recover the two known rejected fixtures. Both were positive definite only at 3-5 radial rings and failed at 6-8; the lower ring counts had large condition numbers (about 70,000-438,000). Do not use those lower-order cases as a validated fix. The annular basis/self-mutual consistency needs redesign; no diagonal loading or weakened Cholesky gate is permitted.

## Rectangular conductor-section diagnostics

- `rectangular_cross_section_gmd.py`: logarithmic geometric-mean distance (GMD) for a uniformly filled rectangular cross-section.
- `rectangular_segment_inductance.py`: finite-length Neumann self term for one straight segment with a uniform rectangular current cross-section, plus the matching mutual term for two contiguous collinear segments; both use analytic axial integration and Gauss-Legendre cross-section averaging.
- `test_rectangular_cross_section_gmd.py` and `test_rectangular_segment_inductance.py`: numerical scaling, symmetry, convergence and limiting checks.
- Arabic derivations: `docs/science/RECTANGULAR_CROSS_SECTION_GMD_NOTE_AR.md` and `docs/science/RECTANGULAR_SEGMENT_SELF_INDUCTANCE_AR.md`.

These are diagnostic primitives only. The segment self term is not a complete closed-loop coil inductance. A complete energy-consistent model still needs all mutual terms between segment/cell current distributions, correct cross-section orientation and return path, plus mesh-refinement and positive-definiteness checks. The segment helper is intentionally not wired into `mono_spiral_disk.py` or the Greenhouse coil estimator; no Coil defaults have changed.
