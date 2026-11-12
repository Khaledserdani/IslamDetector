#!/usr/bin/env bash
set -euo pipefail

# Run matched PI target simulations at four coil-to-target gaps.
# TargetGap is measured from the lower TX winding face (z=30 mm)
# to the upper target face. Each case uses the same pulse and solver settings.
SWEEP_ROOT="${GITHUB_WORKSPACE:-$PWD}/artifacts/elmer-pi-depth-sweep"
RUNNER="${GITHUB_WORKSPACE:-$PWD}/simulation/elmer/run_pi_pulse_foil_surrogate.sh"
mkdir -p "$SWEEP_ROOT"

for gap in 0.045 0.075 0.100 0.150; do
  case_name="gap-$(printf "%0.3f" "$gap" | tr "." "p")"
  echo "=== PI target-gap case: ${gap} m ==="
  TARGET_GAP_M="$gap" OUTPUT_DIR="$SWEEP_ROOT/$case_name" bash "$RUNNER"
done

python3 "$GITHUB_WORKSPACE/simulation/elmer/summarize_pi_target_gap_sweep.py" "$SWEEP_ROOT"
