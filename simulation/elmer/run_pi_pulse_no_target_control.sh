#!/usr/bin/env bash
set -euo pipefail

# Matched control: same air domain, TX winding, pulse, timestep and solver;
# the conductive aluminium target is omitted.
OUTPUT_DIR="${GITHUB_WORKSPACE:-$PWD}/artifacts/elmer-pi-no-target-control"
WORK_DIR="$(mktemp -d)"
mkdir -p "$OUTPUT_DIR"
trap 'rm -rf "$WORK_DIR"' EXIT

cp "$GITHUB_WORKSPACE/simulation/elmer/pi_pulse_separate_coil.geo" "$WORK_DIR/"
cp "$GITHUB_WORKSPACE/simulation/elmer/pi_pulse_separate_coil.sif" "$WORK_DIR/"
cd "$WORK_DIR"

gmsh -2 -format msh2 -setnumber IncludeTarget 0 -o pi-pulse-no-target.msh pi_pulse_separate_coil.geo
ElmerGrid 14 2 pi-pulse-no-target.msh -out pi-pulse-mesh -autoclean
sed '/^Body 3$/,/^End$/d; /^Material 3$/,/^End$/d' pi_pulse_separate_coil.sif > pi-pulse-mesh/islam-pi-pulse.sif
printf 'islam-pi-pulse.sif\n' > pi-pulse-mesh/ELMERSOLVER_STARTINFO

cd pi-pulse-mesh
ElmerSolver 2>&1 | tee "$OUTPUT_DIR/elmersolver-no-target.log"
grep -q "ELMER SOLVER FINISHED AT" "$OUTPUT_DIR/elmersolver-no-target.log"

mapfile -t VTU_FILES < <(find . -type f -name 'islam-pi-pulse*.vtu' -size +0c | sort)
if [ "${#VTU_FILES[@]}" -lt 2 ]; then
  echo "FAIL: expected multiple non-empty no-target VTU snapshots, found ${#VTU_FILES[@]}" >&2
  exit 1
fi
cp "${VTU_FILES[@]}" "$OUTPUT_DIR/"
cp islam-pi-pulse.sif "$OUTPUT_DIR/"
cp "$WORK_DIR/pi_pulse_separate_coil.geo" "$OUTPUT_DIR/"
cp "$WORK_DIR/pi-pulse-no-target.msh" "$OUTPUT_DIR/"
cp mesh.header mesh.nodes mesh.elements mesh.boundary mesh.names "$OUTPUT_DIR/"
python3 "$GITHUB_WORKSPACE/simulation/elmer/verify_pi_pulse_no_target_vtu.py" "$OUTPUT_DIR"
printf 'Control geometry: same axisymmetric air domain and TX winding; Aluminium_Target omitted\nExcitation: same 20-turn homogenized winding and 50-150 us smoothed trapezoidal pulse\nTime steps: 1 us through 200 us, then 20 us through 1 ms (240 steps total)\nPurpose: control run for comparison; not a physical detection-depth claim\n' | tee "$OUTPUT_DIR/reference.txt"
echo "PASS: matched PI no-target control completed with finite fields and no target region"
