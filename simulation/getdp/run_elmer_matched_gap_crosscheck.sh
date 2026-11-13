#!/usr/bin/env bash
set -euo pipefail
ROOT="${GITHUB_WORKSPACE:-$PWD}"
OUT="$ROOT/artifacts/elmer-pi-depth-sweep"
mkdir -p "$OUT/inputs"
python3 - "$ROOT/simulation/elmer/pi_pulse_separate_coil.sif" "$OUT/inputs/pi_pulse_getdp_outer_dirichlet.sif" <<'PY'
from pathlib import Path
import sys
src = Path(sys.argv[1]).read_text(encoding="utf-8")
needle = "Infinity BC = Logical True"
if src.count(needle) != 1:
    raise SystemExit(f"Expected exactly one Infinity BC statement, found {src.count(needle)}")
dst = src.replace(needle, "A = Real 0.0")
Path(sys.argv[2]).write_text(dst, encoding="utf-8")
print("Created Elmer SIF with A=0 outer boundary to match GetDP's finite-domain Dirichlet boundary.")
PY
SIF_TEMPLATE="$OUT/inputs/pi_pulse_getdp_outer_dirichlet.sif" \
MESH_REFINEMENT_DIVISIONS=4 \
bash "$ROOT/simulation/elmer/run_pi_pulse_depth_sweep.sh"
python3 "$ROOT/simulation/getdp/compare_getdp_elmer_gap_sweep.py" \
  "$ROOT/simulation/getdp/results/getdp_pi_target_gap_sweep_2026-11-13.csv" "$OUT"
