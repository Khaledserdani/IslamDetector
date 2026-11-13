#!/usr/bin/env python3
"""Validate coupled PI-to-AFE transient outputs and passive energy balance."""
import json, math, sys
from pathlib import Path
root=Path(sys.argv[1])
m=json.loads((root/"afe_metrics.json").read_text(encoding="utf-8"))
wave=root/"afe_waveform.csv"
if not wave.is_file() or m["sample_count"]<100:
    raise SystemExit("FAIL: AFE waveform missing or too short")
if m["energy_balance_relative_error"]>3e-4:
    raise SystemExit(f"FAIL: AFE energy residual {m['energy_balance_relative_error']}")
for key in ("peak_abs_induced_emf_v","peak_abs_rx_terminal_voltage_v","peak_abs_afe_input_voltage_v"):
    if not math.isfinite(m[key]) or m[key]<0: raise SystemExit(f"FAIL: invalid metric {key}")
print("PASS: RX/AFE waveform and passive energy balance verified")
print(f"AFE input peak: {m['peak_abs_afe_input_voltage_v']:.9g} V; clamp energy: {m['coil_tvs_absorbed_energy_j']+m['input_clamp_absorbed_energy_j']:.9g} J")
