#!/usr/bin/env bash
set -euo pipefail

# Build an axisymmetric PI sensor geometry with a driven TX winding and a
# physically separate aluminium target. No circuit is connected through target.
OUTPUT_DIR="${OUTPUT_DIR:-${GITHUB_WORKSPACE:-$PWD}/artifacts/elmer-pi-pulse-surrogate}"
TARGET_GAP_M="${TARGET_GAP_M:-0.045}"
COIL_INNER_RADIUS_M="${COIL_INNER_RADIUS_M:-0.130}"
COIL_RADIAL_WIDTH_M="${COIL_RADIAL_WIDTH_M:-0.030}"
TARGET_INNER_RADIUS_M="${TARGET_INNER_RADIUS_M:-0.0}"
TARGET_RADIAL_WIDTH_M="${TARGET_RADIAL_WIDTH_M:-0.250}"
TARGET_THICKNESS_M="${TARGET_THICKNESS_M:-0.005}"
MESH_REFINEMENT_DIVISIONS="${MESH_REFINEMENT_DIVISIONS:-3}"
WORK_DIR="$(mktemp -d)"
mkdir -p "$OUTPUT_DIR"
trap 'rm -rf "$WORK_DIR"' EXIT

cp "$GITHUB_WORKSPACE/simulation/elmer/pi_pulse_separate_coil.geo" "$WORK_DIR/"
cp "$GITHUB_WORKSPACE/simulation/elmer/pi_pulse_separate_coil.sif" "$WORK_DIR/"
cd "$WORK_DIR"

gmsh -2 -format msh2 -setnumber TargetGap "$TARGET_GAP_M" -setnumber CoilInnerRadiusM "$COIL_INNER_RADIUS_M" -setnumber CoilRadialWidthM "$COIL_RADIAL_WIDTH_M" -setnumber TargetInnerRadiusM "$TARGET_INNER_RADIUS_M" -setnumber TargetRadialWidthM "$TARGET_RADIAL_WIDTH_M" -setnumber TargetThicknessM "$TARGET_THICKNESS_M" -setnumber MeshRefinementDivisions "$MESH_REFINEMENT_DIVISIONS" -o pi-pulse.msh pi_pulse_separate_coil.geo
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
printf 'Geometry: separate axisymmetric TX coil and aluminium target; coil inner radius %s m; radial width %s m; target inner radius %s m; target radial width %s m; target thickness %s m; coil-target separation %s m; local mesh divisions through target thickness %s\nExcitation: homogenized 20-turn TX winding pack, 1 A peak per turn (20 A-turn total); smooth trapezoidal PI-style current-density pulse, 50 us turn-on and 150 us turn-off\nPeak current density: approximately 6.6667e4 A/m^2 over 3.0e-4 m^2 winding-pack cross-section\nTime steps: 1 us through 200 us, then 20 us through 1 ms (240 steps total)\nModel status: numerical surrogate; pulse is an assumed drive waveform, not a measured hardware current\n' "$COIL_INNER_RADIUS_M" "$COIL_RADIAL_WIDTH_M" "$TARGET_INNER_RADIUS_M" "$TARGET_RADIAL_WIDTH_M" "$TARGET_THICKNESS_M" "$TARGET_GAP_M" "$MESH_REFINEMENT_DIVISIONS" | tee "$OUTPUT_DIR/reference.txt"
echo "PASS: independent TX-to-target PI pulse model produced finite magnetic-field snapshots with bounded decay"
