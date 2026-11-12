#!/usr/bin/env bash
set -euo pipefail

# Run matched PI target simulations at four coil-to-target gaps.
# TargetGap is measured from the lower TX winding face (z=30 mm)
# to the upper target face. Each case uses the same pulse and solver settings.
SWEEP_ROOT="${GITHUB_WORKSPACE:-$PWD}/artifacts/elmer-pi-depth-sweep"
RUNNER="${GITHUB_WORKSPACE:-$PWD}/simulation/elmer/run_pi_pulse_foil_surrogate.sh"
mkdir -p "$SWEEP_ROOT"

for gap in 0.045 0.075 0.100 0.150; do
  case_name="gap-${gap//./p}"
  echo "=== PI target-gap case: ${gap} m ==="
  TARGET_GAP_M="$gap" OUTPUT_DIR="$SWEEP_ROOT/$case_name" bash "$RUNNER"
done

python3 - "$SWEEP_ROOT" <<'PY'
import csv
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for gap in (0.045, 0.075, 0.100, 0.150):
    case = root / f"gap-{str(gap).replace('.', 'p')}"
    path = case / "target_induced_current_summary.csv"
    with path.open(newline="") as handle:
        samples = list(csv.DictReader(handle))
    if not samples:
        raise SystemExit(f"FAIL: no target-current samples in {path}")
    peak = max(samples, key=lambda row: float(row["max_target_current_density_A_per_m2"]))
    final = samples[-1]
    peak_value = float(peak["max_target_current_density_A_per_m2"])
    final_value = float(final["max_target_current_density_A_per_m2"])
    if peak_value <= 0 or final_value >= peak_value * 0.10:
        raise SystemExit(f"FAIL: invalid target-current decay for {gap*1000:.0f} mm")
    rows.append({
        "target_gap_mm": f"{gap*1000:.0f}",
        "peak_step": peak["time_step"],
        "peak_target_current_density_A_per_m2": f"{peak_value:.12g}",
        "final_step": final["time_step"],
        "final_target_current_density_A_per_m2": f"{final_value:.12g}",
        "final_to_peak_ratio": f"{final_value/peak_value:.8g}",
    })

summary = root / "pi_target_gap_sweep_summary.csv"
with summary.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f"PASS: four matched target-gap cases summarized in {summary}")
for row in rows:
    print(
        f"{row['target_gap_mm']} mm: peak J="
        f"{row['peak_target_current_density_A_per_m2']} A/m^2 "
        f"(step {row['peak_step']})"
    )
PY
