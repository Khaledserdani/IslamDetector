#!/usr/bin/env bash
set -euo pipefail

# Re-run ElmerCSC's official two-coil MagnetoDynamics reference at a pinned revision.
ELMER_REVISION="16093051a4d21061692885eb9df9cb98688d2da2"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

git clone --quiet --filter=blob:none --no-checkout https://github.com/ElmerCSC/elmerfem.git "$WORK_DIR/elmerfem"
git -C "$WORK_DIR/elmerfem" checkout --quiet "$ELMER_REVISION"

CASE_DIR="$WORK_DIR/elmerfem/fem/tests/mgdyn_steady_coils"
cd "$CASE_DIR"

command -v ElmerGrid >/dev/null
command -v ElmerSolver >/dev/null

# The upstream test supplies a structured 2D grid; generate the solver mesh.
ElmerGrid 1 2 coils.grd 2>&1 | tee "$WORK_DIR/elmergrid.log"

# Run the upstream case without changing its SIF or material/source definitions.
ElmerSolver 2>&1 | tee "$WORK_DIR/elmersolver.log"

grep -q "ELMER SOLVER FINISHED AT" "$WORK_DIR/elmersolver.log"
if ! find . -maxdepth 1 -type f -name 'case*.vtu' -size +0c -print -quit | grep -q .; then
  echo "FAIL: Elmer completed but no non-empty VTU field output was produced" >&2
  exit 1
fi

echo "PASS: pinned Elmer two-coil MagnetoDynamics reference completed and produced VTU output"
echo "Elmer upstream revision: $ELMER_REVISION"
