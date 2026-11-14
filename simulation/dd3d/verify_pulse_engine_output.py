#!/usr/bin/env python3
"""Check the archived PI pulse sample run and its numerical energy balance."""
import csv
import json
import math
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: verify_pulse_engine_output.py OUTPUT_DIRECTORY")
root = Path(sys.argv[1])
metrics_path = root / "pulse_metrics.json"
wave_path = root / "pulse_waveform.csv"
if not metrics_path.is_file() or not wave_path.is_file():
    raise SystemExit("FAIL: pulse metrics or waveform CSV is missing")
metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
with wave_path.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
if len(rows) != metrics["sample_count"] or len(rows) < 100:
    raise SystemExit("FAIL: waveform row count does not match the simulation summary")
if metrics["energy_balance_relative_error"] > 3e-4:
    raise SystemExit("FAIL: energy-balance residual exceeds 0.03%")
for key in (
    "peak_abs_tx_current_a",
    "tx_current_at_turnoff_a",
    "peak_abs_target_loop_current_a",
    "peak_abs_rx_voltage_v",
    "peak_abs_rx_voltage_after_turnoff_v",
):
    if not math.isfinite(metrics[key]) or metrics[key] <= 0:
        raise SystemExit(f"FAIL: invalid positive metric {key}")
for row in rows:
    for value in row.values():
        if not math.isfinite(float(value)):
            raise SystemExit("FAIL: waveform contains a non-finite value")
print(f"PASS: {len(rows)} pulse samples; energy residual {metrics['energy_balance_relative_error']:.6%}")
print("NOTE: this is a synthetic coaxial-loop sample, not the DD32 winding or a measured hardware pulse.")
