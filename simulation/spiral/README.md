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
