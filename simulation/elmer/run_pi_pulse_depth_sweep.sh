#!/usr/bin/env bash
set -euo pipefail

# Run matched PI target simulations at four coil-to-target gaps.
# TargetGap is measured from the lower TX winding face (z=30 mm)
# to the upper target face. Each case uses the same pulse and solver settings.
SWEEP_ROOT="${GITHUB_WORKSPACE:-$PWD}/artifacts/elmer-pi-depth-sweep"
RUNNER="${GITHUB_WORKSPACE:-$PWD}/simulation/elmer/run_pi_pulse_foil_surrogate.sh"
mkdir -p "$SWEEP_ROOT"

SIF_TEMPLATE="${SIF_TEMPLATE:-${GITHUB_WORKSPACE:-$PWD}/simulation/elmer/pi_pulse_separate_coil.sif}"
MESH_REFINEMENT_DIVISIONS="${MESH_REFINEMENT_DIVISIONS:-4}"
for gap in 0.045 0.075 0.100 0.150; do
  case_name="gap-$(printf "%0.3f" "$gap" | tr "." "p")"
  echo "=== PI target-gap case: ${gap} m ==="
  SIF_TEMPLATE="$SIF_TEMPLATE" MESH_REFINEMENT_DIVISIONS="$MESH_REFINEMENT_DIVISIONS" TARGET_GAP_M="$gap" OUTPUT_DIR="$SWEEP_ROOT/$case_name" bash "$RUNNER"
done

python3 "$GITHUB_WORKSPACE/simulation/elmer/summarize_pi_target_gap_sweep.py" "$SWEEP_ROOT"

# Keep the complete time-series CSVs and only the peak/final field snapshots.
# The raw 240-file VTU sets otherwise create a >500 MB artifact that cannot
# be downloaded for review. Preserve enough data for audit and visualization.
python3 - "$SWEEP_ROOT" <<'PY'
import csv
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
for case_dir in sorted(root.glob("gap-*")):
    summary = case_dir / "target_current_axisymmetric_summary.csv"
    if not summary.is_file():
        raise SystemExit(f"FAIL: missing axisymmetric summary before compaction: {summary}")
    with summary.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"FAIL: empty axisymmetric summary: {summary}")
    peak = max(rows, key=lambda row: float(row["rms_target_current_density_A_per_m2"]))
    final = max(rows, key=lambda row: int(row["time_step"]))
    keep = {int(peak["time_step"]), int(final["time_step"])}
    for path in case_dir.glob("islam-pi-pulse_t*.vtu"):
        match = re.search(r"_t(\d+)\.vtu$", path.name)
        if not match or int(match.group(1)) not in keep:
            path.unlink()
    remaining = list(case_dir.glob("islam-pi-pulse_t*.vtu"))
    if len(remaining) != len(keep):
        raise SystemExit(f"FAIL: expected peak/final VTU snapshots in {case_dir}, found {len(remaining)}")
    print(f"Compacted {case_dir.name}: kept peak step {int(peak['time_step'])} and final step {int(final['time_step'])}")
PY
