#!/usr/bin/env bash
set -euo pipefail

# Run a normalized Gaussian current-pulse surrogate on Elmer's conductive-foil reference mesh.
ELMER_REVISION="16093051a4d21061692885eb9df9cb98688d2da2"
WORK_DIR="$(mktemp -d)"
OUTPUT_DIR="${GITHUB_WORKSPACE:-$PWD}/artifacts/elmer-pi-pulse-surrogate"
mkdir -p "$OUTPUT_DIR"
trap 'rm -rf "$WORK_DIR"' EXIT

git clone --quiet --filter=blob:none --no-checkout https://github.com/ElmerCSC/elmerfem.git "$WORK_DIR/elmerfem"
git -C "$WORK_DIR/elmerfem" checkout --quiet "$ELMER_REVISION"

CASE_DIR="$WORK_DIR/elmerfem/fem/tests/circuits2D_transient_foil"
cp "$GITHUB_WORKSPACE/simulation/elmer/pi_pulse_foil.sif" "$CASE_DIR/islam-pi-pulse.sif"
cp "$GITHUB_WORKSPACE/simulation/elmer/pi_pulse_current_source.definitions" "$CASE_DIR/sif/islam-pi-current-source.definitions"
printf 'islam-pi-pulse.sif\n' > "$CASE_DIR/ELMERSOLVER_STARTINFO"
cd "$CASE_DIR"

ElmerSolver 2>&1 | tee "$OUTPUT_DIR/elmersolver-pi-pulse.log"
grep -q "ELMER SOLVER FINISHED AT" "$OUTPUT_DIR/elmersolver-pi-pulse.log"

mapfile -t VTU_FILES < <(find . -type f -name 'islam-pi-pulse*.vtu' -size +0c | sort)
if [ "${#VTU_FILES[@]}" -lt 2 ]; then
  echo "FAIL: expected multiple non-empty transient VTU outputs, found ${#VTU_FILES[@]}" >&2
  exit 1
fi
cp "${VTU_FILES[@]}" "$OUTPUT_DIR/"
cp "$CASE_DIR/islam-pi-pulse.sif" "$OUTPUT_DIR/"
cp "$CASE_DIR/1383/mesh.header" "$CASE_DIR/1383/mesh.nodes" "$CASE_DIR/1383/mesh.elements" "$CASE_DIR/1383/mesh.boundary" "$CASE_DIR/1383/mesh.names" "$OUTPUT_DIR/"
python3 "$GITHUB_WORKSPACE/simulation/elmer/verify_pi_pulse_vtu.py" "$OUTPUT_DIR"
printf 'Elmer upstream revision: %s\nSource fixture: circuits2D_transient_foil\nExcitation: normalized zero-mean bipolar Gaussian voltage pulse, center 200 us, sigma 50 us\nTime step: 10 us; total simulated time: 1 ms\n' "$ELMER_REVISION" | tee "$OUTPUT_DIR/reference.txt"
echo "PASS: Elmer normalized PI pulse surrogate produced time-varying finite magnetic-flux-density fields"
