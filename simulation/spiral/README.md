# Mono Spiral 35x35 reference geometry

Run the unit tests from this directory:

```bash
python -m unittest -v
```

The model represents 13 concentric square current loops with 350 mm outer side,
1.20 mm centre-to-centre pitch and 0.60 mm wire. It calculates path length,
cold copper resistance at 20 C, and a magnetostatic Biot-Savart field estimate.

Limitations:
- The short radial transition between adjacent turns and the cable leads are
  excluded from copper length and field.
- Turns are represented as ideal filament loops.
- No PI switching waveform, target eddy currents, soil, receiver input loading,
  clamp or analogue front end is included.
- This is a geometry and field-kernel baseline, not a detection-depth model.

## Additional transient and target models

- `mono_spiral_transient.py`: first-order coupled primary/target RL model.
- `mono_spiral_disk.py`: multi-ring conducting-disk surrogate with mutual
  inductance between the square winding and concentric eddy-current loops.
- `test_mono_spiral_disk.py`: target-surrogate regression tests.

Run all tests with `python -m unittest -v`. The latest validated revision
ran 15 tests successfully in GitHub Actions (commit
`f0931762eef1e365d2952dba3a4797bf3eebec35`). Documentation-only commits may
not trigger the simulation workflow.

The disk model is a reduced-order axisymmetric approximation, not 3-D FEM.
It uses equal-area annuli and currently rejects more than 8 target rings because
higher refinement produced a numerically unreliable response in the present
thin-ring approximation. The target values in tests are synthetic fixtures,
not selected field targets. No detection depth, metal classification, soil
performance or hardware safety claim follows from these tests.

The latest validated run passed 16 unit tests and completed separate angular
and radial sensitivity sweeps. The angular sweep changed by about 0.063% from
96 to 128 segments per ring, while the radial sweep still changed by about
0.676% from 7 to 8 rings; radial convergence is therefore not established.
See `docs/science/MONO_SPIRAL_DISK_SURROGATE_CONVERGENCE_AR.md`.
