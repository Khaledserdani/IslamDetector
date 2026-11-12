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
    integrated=[float(x["integral_abs_J_dV_A"]) for x in samples]
    rms=[float(x["volume_weighted_rms_J_A_per_m2"]) for x in samples]
    if not all(v >= 0 for v in integrated+rms) or max(integrated) <= 0:
        raise SystemExit(f"FAIL: invalid volume-integrated response for {name}")
    peak_index=max(range(len(integrated)),key=integrated.__getitem__)
    rows.append((name,len(samples),max(values),max(integrated),samples[peak_index]["time_step"],integrated[-1],max(rms)))
with (root/"target_geometry_comparison.csv").open("w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["target","time_samples","peak_max_J_A_per_m2","peak_integral_abs_J_dV_A","peak_time_step","final_integral_abs_J_dV_A","peak_volume_weighted_rms_J_A_per_m2","evidence_class"])
    for name,n,peak_j,peak_integral,step,final_integral,peak_rms in rows:
        w.writerow([name,n,peak_j,peak_integral,step,final_integral,peak_rms,"simulated; axisymmetric aluminium surrogate"])
print("PASS: coin, ring and large-target responses extracted")
for name,n,peak_j,peak_integral,step,final_integral,peak_rms in rows:
    print(f"{name}: peak max|J|={peak_j:.8g} A/m^2; peak integral|J|dV={peak_integral:.8g} A at step {step}; final integral={final_integral:.8g} A; peak RMS={peak_rms:.8g} A/m^2")
print("CAUTION: response values are not detection probability, receiver SNR, or depth.")
PY
