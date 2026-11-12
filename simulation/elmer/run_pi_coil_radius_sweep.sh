#!/usr/bin/env bash
set -euo pipefail
ROOT="${GITHUB_WORKSPACE:-$PWD}"
BASE="${ROOT}/artifacts/elmer-coil-radius-sweep"
mkdir -p "$BASE"
# Three mean diameters: 190, 290 (current reference), and 350 mm.
# The winding pack cross-section and excitation remain unchanged.
for radius in 0.080 0.130 0.160; do
  tag="$(printf '%s' "$radius" | tr '.' 'p')"
  echo "=== TX inner radius ${radius} m ==="
  OUTPUT_DIR="$BASE/coil-inner-${tag}" \
  COIL_INNER_RADIUS_M="$radius" \
  COIL_RADIAL_WIDTH_M="0.030" \
  TARGET_GAP_M="0.075" \
    bash "$ROOT/simulation/elmer/run_pi_pulse_foil_surrogate.sh"
done
python3 - "$BASE" <<'PY'
import csv, pathlib, sys
root=pathlib.Path(sys.argv[1])
rows=[]
for d in sorted(root.glob("coil-inner-*")):
    radius=float(d.name.removeprefix("coil-inner-").replace("p","."))
    # Numerical field extraction is deliberately not inferred from screenshots/log text.
    vtu=list(d.glob("islam-pi-pulse_t*.vtu"))
    if len(vtu) != 240:
        raise SystemExit(f"FAIL: {d.name}: expected 240 VTU snapshots, got {len(vtu)}")
    rows.append((radius, 2*(radius+0.015), len(vtu), "simulated; foil surrogate"))
with (root/"coil_radius_sweep_inventory.csv").open("w", newline="") as f:
    w=csv.writer(f); w.writerow(["coil_inner_radius_m","mean_diameter_m","vtu_snapshots","evidence_class"]); w.writerows(rows)
if len(rows)!=3: raise SystemExit(f"FAIL: expected 3 geometry cases, got {len(rows)}")
print("PASS: all three controlled coil-radius cases completed; inventory written")
for r in rows: print(f"inner radius {r[0]:.3f} m; mean diameter {r[1]*1000:.0f} mm; {r[2]} snapshots")
PY
