#!/usr/bin/env bash
set -euo pipefail

# Re-run ElmerCSC's transient axisymmetric coil-to-conductive-foil reference.
ELMER_REVISION="16093051a4d21061692885eb9df9cb98688d2da2"
WORK_DIR="$(mktemp -d)"
OUTPUT_DIR="${GITHUB_WORKSPACE:-$PWD}/artifacts/elmer-transient-foil"
mkdir -p "$OUTPUT_DIR"
trap 'rm -rf "$WORK_DIR"' EXIT

git clone --quiet --filter=blob:none --no-checkout https://github.com/ElmerCSC/elmerfem.git "$WORK_DIR/elmerfem"
git -C "$WORK_DIR/elmerfem" checkout --quiet "$ELMER_REVISION"

CASE_DIR="$WORK_DIR/elmerfem/fem/tests/circuits2D_transient_foil"
SIF="$CASE_DIR/sif/1383-components-foilwinding.sif"
grep -q 'Simulation Type = Transient' "$SIF"
grep -q 'Electric Conductivity = 1e7' "$SIF"
grep -q 'Coil Type = String Foil Winding' "$SIF"

cd "$CASE_DIR"
command -v ElmerSolver >/dev/null
ElmerSolver 2>&1 | tee "$OUTPUT_DIR/elmersolver-transient-foil.log"

grep -q "ELMER SOLVER FINISHED AT" "$OUTPUT_DIR/elmersolver-transient-foil.log"
grep -q "CompareToReferenceSolution: Solver 1 PASSED:" "$OUTPUT_DIR/elmersolver-transient-foil.log"
grep -q "CompareToReferenceSolution: Solver 3 PASSED:" "$OUTPUT_DIR/elmersolver-transient-foil.log"
if grep -q "CompareToReferenceSolution: Solver .* FAILED:" "$OUTPUT_DIR/elmersolver-transient-foil.log"; then
  echo "FAIL: Elmer transient conductive-foil reference norm failed" >&2
  exit 1
fi

cp "$SIF" "$OUTPUT_DIR/"
cp sif/1383-circuits-components.definitions "$OUTPUT_DIR/"
cp 1383/mesh.header 1383/mesh.nodes 1383/mesh.elements 1383/mesh.boundary 1383/mesh.names "$OUTPUT_DIR/"
printf 'Elmer upstream revision: %s\nCase: circuits2D_transient_foil\n' "$ELMER_REVISION" | tee "$OUTPUT_DIR/reference.txt"
echo "PASS: transient axisymmetric winding-to-aluminium-foil reference passed both reference norms"
