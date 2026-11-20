#!/usr/bin/env bash
set -euo pipefail
ROOT="${GITHUB_WORKSPACE:-$PWD}"
BASE="${ROOT}/artifacts/elmer-coil-radius-sweep"
mkdir -p "$BASE"
# Three mean diameters: 190, 290 (current reference), and 350 mm.
# Winding-pack cross-section and imposed excitation are held constant.
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
    vtu=list(d.glob("islam-pi-pulse_t*.vtu"))
    if len(vtu) != 240:
        raise SystemExit(f"FAIL: {d.name}: expected 240 VTU snapshots, got {len(vtu)}")
    summary=d/"target_induced_current_summary.csv"
    if not summary.is_file():
        raise SystemExit(f"FAIL: missing numerical target-current summary in {d.name}")
    with summary.open(newline="") as f:
        samples=list(csv.DictReader(f))
    if len(samples) != 240:
        raise SystemExit(f"FAIL: expected 240 target-current samples in {d.name}, got {len(samples)}")
    peak=max(float(x["max_target_current_density_A_per_m2"]) for x in samples)
    if not peak > 0:
        raise SystemExit(f"FAIL: non-positive target-current response in {d.name}")
    peak_step=max(samples,key=lambda x:float(x["max_target_current_density_A_per_m2"]))["time_step"]
    rows.append((radius, 2*(radius+0.015), len(vtu), peak, peak_step, "simulated; aluminium foil surrogate"))
with (root/"coil_radius_sweep_comparison.csv").open("w", newline="") as f:
    w=csv.writer(f)
    w.writerow(["coil_inner_radius_m","mean_diameter_m","vtu_snapshots","peak_target_current_density_A_per_m2","peak_time_step","evidence_class"])
    w.writerows(rows)
if len(rows)!=3: raise SystemExit(f"FAIL: expected 3 geometry cases, got {len(rows)}")
print("PASS: numerical comparison extracted for all three coil geometries")
for r in rows: print(f"mean diameter {r[1]*1000:.0f} mm; peak target J={r[3]:.8g} A/m^2 at step {r[4]}")
print("CAUTION: ranking is conditional on equal imposed ampere-turns and the simplified foil target; it is not a real detection-depth result.")
PY
