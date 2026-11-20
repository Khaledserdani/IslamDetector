#!/usr/bin/env bash
set -euo pipefail

ROOT="${GITHUB_WORKSPACE:-$PWD}"
OUT_ROOT="$ROOT/artifacts/elmer-pi-mesh-convergence"
RUNNER="$ROOT/simulation/elmer/run_pi_pulse_foil_surrogate.sh"
mkdir -p "$OUT_ROOT"

# Two representative gaps; three nested local target/coil refinement levels.
for gap_mm in 45 100; do
  gap_m="$(awk -v mm="$gap_mm" 'BEGIN { printf "%.3f", mm/1000 }')"
  for divisions in 3 5 8; do
    case_dir="$OUT_ROOT/gap-${gap_mm}mm/n${divisions}"
    echo "=== mesh convergence: gap=${gap_mm} mm, target-thickness divisions=${divisions} ==="
    TARGET_GAP_M="$gap_m" MESH_REFINEMENT_DIVISIONS="$divisions" OUTPUT_DIR="$case_dir" bash "$RUNNER"
  done
done

python3 "$ROOT/simulation/elmer/analyze_pi_mesh_convergence.py" "$OUT_ROOT"

# Preserve CSVs, logs, mesh metadata and the peak/final VTU snapshots only.
python3 - "$OUT_ROOT" <<'PY'
import csv, re, sys
from pathlib import Path
root = Path(sys.argv[1])
for case in sorted(p for p in root.glob("gap-*/*") if p.is_dir()):
    summary = case / "target_induced_current_summary.csv"
    with summary.open(newline="") as f:
        rows = list(csv.DictReader(f))
    peak = max(rows, key=lambda r: float(r["volume_weighted_rms_J_A_per_m2"]))
    final = max(rows, key=lambda r: int(r["time_step"]))
    keep = {int(peak["time_step"]), int(final["time_step"])}
    for vtu in case.glob("islam-pi-pulse_t*.vtu"):
        match = re.search(r"_t(\d+)\.vtu$", vtu.name)
        if not match or int(match.group(1)) not in keep:
            vtu.unlink()
    remaining = {int(re.search(r"_t(\d+)\.vtu$", p.name).group(1))
                 for p in case.glob("islam-pi-pulse_t*.vtu")}
    if remaining != keep:
        raise SystemExit(f"FAIL: incorrect retained snapshots in {case}")
    print(f"Compacted {case.relative_to(root)}: retained peak/final snapshots {sorted(keep)}")
PY
