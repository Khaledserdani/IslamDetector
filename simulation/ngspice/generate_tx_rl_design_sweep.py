#!/usr/bin/env python3
"""Generate a bounded analytic TX RL sweep; no hardware rating is inferred."""
import csv
import math
from pathlib import Path

RESISTANCE_OHM = 1.52  # theoretical copper DCR estimate at 20 C, not measured
INDUCTANCES_H = (300e-6, 350e-6, 400e-6)
BUS_VOLTAGES_V = (5.0, 12.0)  # comparison cases only, not approved supply choices
PULSE_WIDTHS_S = (50e-6, 100e-6, 200e-6)

out = Path("artifacts/dd32-tx-analytic-sweep")
out.mkdir(parents=True, exist_ok=True)
rows = []
for voltage in BUS_VOLTAGES_V:
    for inductance in INDUCTANCES_H:
        tau = inductance / RESISTANCE_OHM
        for pulse in PULSE_WIDTHS_S:
            current = voltage / RESISTANCE_OHM * (1.0 - math.exp(-pulse / tau))
            energy = 0.5 * inductance * current * current
            rows.append({
                "voltage_V_comparison_only": voltage,
                "inductance_uH": inductance * 1e6,
                "resistance_ohm_theoretical": RESISTANCE_OHM,
                "pulse_us": pulse * 1e6,
                "tau_us": tau * 1e6,
                "peak_current_A_ideal": current,
                "stored_energy_mJ_ideal": energy * 1e3,
            })

for voltage in BUS_VOLTAGES_V:
    subset = [r for r in rows if r["voltage_V_comparison_only"] == voltage]
    for lval in INDUCTANCES_H:
        currents = [r["peak_current_A_ideal"] for r in subset if r["inductance_uH"] == lval * 1e6]
        if not all(a < b for a, b in zip(currents, currents[1:])):
            raise SystemExit("FAIL: ideal current must increase with pulse width")
if not all(math.isfinite(v) and v >= 0 for row in rows
           for v in (row["peak_current_A_ideal"], row["stored_energy_mJ_ideal"])):
    raise SystemExit("FAIL: non-finite or negative sweep result")

path = out / "dd32_tx_rl_sweep.csv"
with path.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f"PASS: generated {len(rows)} ideal RL comparison points -> {path}")
print("WARNING: comparison only; measured DCR/L, real pulse, switching and clamp are not modeled")
