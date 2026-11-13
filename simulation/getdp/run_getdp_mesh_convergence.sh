#!/usr/bin/env bash
set -euo pipefail
ROOT="${GITHUB_WORKSPACE:-$PWD}"
OUT="$ROOT/artifacts/getdp-mesh-convergence"
mkdir -p "$OUT"
command -v gmsh
command -v getdp
getdp -version 2>&1 | tee "$OUT/getdp-version.txt" || true
python3 --version | tee "$OUT/python-version.txt"
for divisions in 3 4 6; do
  case_dir="$OUT/gap-45mm-refine-$divisions"
  mkdir -p "$case_dir"
  echo "=== GetDP mesh convergence: gap 45 mm, target thickness divisions $divisions ==="
  gmsh -2 "$ROOT/simulation/elmer/pi_pulse_separate_coil.geo" \
    -setnumber TargetGap 0.045 \
    -setnumber MeshRefinementDivisions "$divisions" \
    -format msh2 -o "$case_dir/model.msh" > "$case_dir/gmsh.log" 2>&1
  cp "$ROOT/simulation/getdp/pi_pulse_axisymmetric.pro" "$case_dir/model.pro"
  (
    cd "$case_dir"
    getdp "$case_dir/model.pro" -msh "$case_dir/model.msh" -solve Mag -pos Map > getdp.log 2>&1
    grep -q "Stopped" getdp.log
    test -s j2.txt
    echo "J2_TABLE_PREVIEW divisions=$divisions"
    sed -n '1,12p' j2.txt
  )
done
python3 "$ROOT/simulation/getdp/analyze_getdp_mesh_convergence.py" "$OUT"
