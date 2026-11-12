#!/usr/bin/env bash
set -euo pipefail
ROOT="${GITHUB_WORKSPACE:-$PWD}"
BASE="${ROOT}/artifacts/elmer-target-geometry-sweep"
mkdir -p "$BASE"

# Controlled geometry comparison at 75 mm coil-to-target gap.
# Coin: 24 mm diameter, 2 mm thick solid aluminium disk.
# Ring: 20 mm inner diameter, 25 mm outer diameter, 1.5 mm thick annulus.
# Large target: 300 mm diameter, 5 mm thick disk.
run_case() {
  local name="$1" inner="$2" width="$3" thickness="$4"
  echo "=== Target: $name ==="
  OUTPUT_DIR="$BASE/$name" \
  TARGET_GAP_M="0.075" \
  COIL_INNER_RADIUS_M="0.130" \
  COIL_RADIAL_WIDTH_M="0.030" \
  TARGET_INNER_RADIUS_M="$inner" \
  TARGET_RADIAL_WIDTH_M="$width" \
  TARGET_THICKNESS_M="$thickness" \
    bash "$ROOT/simulation/elmer/run_pi_pulse_foil_surrogate.sh"
}
run_case coin_24mm 0.000 0.012 0.002
run_case ring_20x25mm 0.010 0.0025 0.0015
run_case large_disk_300mm 0.000 0.150 0.005

python3 - "$BASE" <<'PY'
import csv, pathlib, sys
root=pathlib.Path(sys.argv[1])
rows=[]
for name in ("coin_24mm","ring_20x25mm","large_disk_300mm"):
    d=root/name
    summary=d/"target_induced_current_summary.csv"
    if not summary.is_file():
        raise SystemExit(f"FAIL: missing target-current summary for {name}")
    with summary.open(newline="") as f:
        samples=list(csv.DictReader(f))
    if len(samples) != 240:
        raise SystemExit(f"FAIL: expected 240 time samples for {name}, got {len(samples)}")
    values=[float(x["max_target_current_density_A_per_m2"]) for x in samples]
    if not all(v >= 0 for v in values) or max(values) <= 0:
        raise SystemExit(f"FAIL: invalid induced-current response for {name}")
    peak_index=max(range(len(values)),key=values.__getitem__)
    rows.append((name,len(samples),max(values),samples[peak_index]["time_step"],values[-1]))
with (root/"target_geometry_comparison.csv").open("w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["target","time_samples","peak_current_density_A_per_m2","peak_time_step","final_current_density_A_per_m2","evidence_class"])
    for name,n,peak,step,final in rows:
        w.writerow([name,n,peak,step,final,"simulated; axisymmetric aluminium surrogate"])
print("PASS: coin, ring and large-target responses extracted")
for name,n,peak,step,final in rows:
    print(f"{name}: peak J={peak:.8g} A/m^2 at step {step}; final={final:.8g} A/m^2")
print("CAUTION: response values are not detection probability, receiver SNR, or depth.")
PY
