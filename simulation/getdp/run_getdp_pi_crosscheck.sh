#!/usr/bin/env bash
set -euo pipefail
ROOT="${GITHUB_WORKSPACE:-$PWD}"
OUT="$ROOT/artifacts/getdp-pi-crosscheck"
mkdir -p "$OUT"
command -v gmsh
command -v getdp
getdp -version 2>&1 | tee "$OUT/getdp-version.txt" || getdp -help 2>&1 | head -30 | tee "$OUT/getdp-version.txt"
python3 --version | tee "$OUT/python-version.txt"

# Same axisymmetric TX/target geometry and material/drive assumptions as the
# existing Elmer PI surrogate. Gaps are measured from TX lower face (z=30 mm)
# to target upper face, matching the Elmer sweep convention.
for gap_mm in 45 75 100 150; do
  case_dir="$OUT/gap-${gap_mm}mm"
  mkdir -p "$case_dir"
  gmsh -2 "$ROOT/simulation/elmer/pi_pulse_separate_coil.geo" \
    -setnumber TargetGap "$(python3 -c "print($gap_mm/1000)")" \
    -setnumber MeshRefinementDivisions 4 \
    -format msh2 -o "$case_dir/model.msh" > "$case_dir/gmsh.log" 2>&1
  # GetDP writes PostOperation files beside the .pro file. Keep one copy per
  # gap so the raw J2 table and fields are archived with that run.
  cp "$ROOT/simulation/getdp/pi_pulse_axisymmetric.pro" "$case_dir/model.pro"
  (
    cd "$case_dir"
    getdp "$case_dir/model.pro" -msh "$case_dir/model.msh" -solve Mag -pos Map > getdp.log 2>&1
    grep -q "Stopped" getdp.log
    test -s j2.txt
  )
done

python3 "$ROOT/simulation/getdp/analyze_getdp_pi_sweep.py" "$OUT"
