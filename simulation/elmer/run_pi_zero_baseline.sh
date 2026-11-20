#!/usr/bin/env bash
set -euo pipefail
ELMER_REVISION="16093051a4d21061692885eb9df9cb98688d2da2"
WORK_DIR="$(mktemp -d)"
OUTPUT_DIR="${GITHUB_WORKSPACE:-$PWD}/artifacts/elmer-pi-zero-baseline"
mkdir -p "$OUTPUT_DIR"
trap 'rm -rf "$WORK_DIR"' EXIT
git clone --quiet --filter=blob:none --no-checkout https://github.com/ElmerCSC/elmerfem.git "$WORK_DIR/elmerfem"
git -C "$WORK_DIR/elmerfem" checkout --quiet "$ELMER_REVISION"
CASE_DIR="$WORK_DIR/elmerfem/fem/tests/circuits2D_transient_foil"
cp "$GITHUB_WORKSPACE/simulation/elmer/pi_pulse_foil.sif" "$CASE_DIR/islam-pi-zero.sif"
cp "$GITHUB_WORKSPACE/simulation/elmer/pi_pulse_current_source.definitions" "$CASE_DIR/sif/islam-pi-zero-current-source.definitions"
sed -i 's/islam-pi-current-source\.definitions/islam-pi-zero-current-source.definitions/' "$CASE_DIR/islam-pi-zero.sif"
sed -i 's/islam-pi-pulse/islam-pi-zero/g' "$CASE_DIR/islam-pi-zero.sif"
sed -i 's/^\$ Is = 1$/\$ Is = 0/' "$CASE_DIR/sif/islam-pi-zero-current-source.definitions"
printf 'islam-pi-zero.sif\n' > "$CASE_DIR/ELMERSOLVER_STARTINFO"
cd "$CASE_DIR"
ElmerSolver 2>&1 | tee "$OUTPUT_DIR/elmersolver-zero-baseline.log"
grep -q "ELMER SOLVER FINISHED AT" "$OUTPUT_DIR/elmersolver-zero-baseline.log"
mapfile -t VTU_FILES < <(find . -type f -name 'islam-pi-zero*.vtu' -size +0c | sort)
if [ "${#VTU_FILES[@]}" -lt 2 ]; then
  echo "FAIL: expected multiple non-empty zero-excitation VTU outputs, found ${#VTU_FILES[@]}" >&2
  exit 1
fi
cp "${VTU_FILES[@]}" "$OUTPUT_DIR/"
cp "$CASE_DIR/islam-pi-zero.sif" "$OUTPUT_DIR/"
cp "$CASE_DIR/1383/mesh.header" "$CASE_DIR/1383/mesh.nodes" "$CASE_DIR/1383/mesh.elements" "$CASE_DIR/1383/mesh.boundary" "$CASE_DIR/1383/mesh.names" "$OUTPUT_DIR/"
python3 "$GITHUB_WORKSPACE/simulation/elmer/verify_pi_zero_baseline.py" "$OUTPUT_DIR"
printf 'Elmer upstream revision: %s\nSource fixture: circuits2D_transient_foil\nExcitation: zero-current control (Is=0)\nTime step: 25 us; total simulated time: 1 ms\n' "$ELMER_REVISION" | tee "$OUTPUT_DIR/reference.txt"
echo "PASS: zero-excitation baseline remained finite and within the zero-field tolerance"
