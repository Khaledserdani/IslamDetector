#!/usr/bin/env bash
set -euo pipefail

# Build an axisymmetric PI sensor geometry with a driven TX winding and a
# physically separate aluminium target. No circuit is connected through target.
OUTPUT_DIR="${GITHUB_WORKSPACE:-$PWD}/artifacts/elmer-pi-pulse-surrogate"
WORK_DIR="$(mktemp -d)"
mkdir -p "$OUTPUT_DIR"
trap 'rm -rf "$WORK_DIR"' EXIT

cp "$GITHUB_WORKSPACE/simulation/elmer/pi_pulse_separate_coil.geo" "$WORK_DIR/"
cp "$GITHUB_WORKSPACE/simulation/elmer/pi_pulse_separate_coil.sif" "$WORK_DIR/"
cd "$WORK_DIR"

gmsh -2 -format msh2 -o pi-pulse.msh pi_pulse_separate_coil.geo
ElmerGrid 14 2 pi-pulse.msh -out pi-pulse-mesh -autoclean
cp pi_pulse_separate_coil.sif pi-pulse-mesh/islam-pi-pulse.sif
printf 'islam-pi-pulse.sif\n' > pi-pulse-mesh/ELMERSOLVER_STARTINFO

cd pi-pulse-mesh
ElmerSolver 2>&1 | tee "$OUTPUT_DIR/elmersolver-pi-pulse.log"
grep -q "ELMER SOLVER FINISHED AT" "$OUTPUT_DIR/elmersolver-pi-pulse.log"

mapfile -t VTU_FILES < <(find . -type f -name 'islam-pi-pulse*.vtu' -size +0c | sort)
if [ "${#VTU_FILES[@]}" -lt 2 ]; then
  echo "FAIL: expected multiple non-empty transient VTU outputs, found ${#VTU_FILES[@]}" >&2
  exit 1
fi
cp "${VTU_FILES[@]}" "$OUTPUT_DIR/"
cp islam-pi-pulse.sif "$OUTPUT_DIR/"
cp "$WORK_DIR/pi_pulse_separate_coil.geo" "$OUTPUT_DIR/"
cp "$WORK_DIR/pi-pulse.msh" "$OUTPUT_DIR/"
cp mesh.header mesh.nodes mesh.elements mesh.boundary mesh.names "$OUTPUT_DIR/"
python3 "$GITHUB_WORKSPACE/simulation/elmer/verify_pi_pulse_vtu.py" "$OUTPUT_DIR"
printf 'Geometry: separate axisymmetric TX coil and aluminium target; coil-target separation 45 mm\nExcitation: normalized Gaussian current-density pulse, peak 1.0e6 A/m^2, center 200 us, sigma 50 us\nTime step: 25 us; total simulated time: 1 ms\n' | tee "$OUTPUT_DIR/reference.txt"
echo "PASS: independent TX-to-target PI pulse model produced finite magnetic-field snapshots with bounded decay"
