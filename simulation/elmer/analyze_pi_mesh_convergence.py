#!/usr/bin/env python3
"""Compare PI target response across three local mesh refinements and two gaps."""
import csv
import math
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) == 2 else None
if ROOT is None:
    raise SystemExit("usage: analyze_pi_mesh_convergence.py OUTPUT_ROOT")

GAPS_MM = (45, 100)
DIVISIONS = (3, 5, 8)
rows = []

def fail(message):
    raise SystemExit(f"FAIL: {message}")

def read_times(sif_path):
    text = sif_path.read_text(encoding="utf-8")
    sm = re.search(r"Timestep\s+Sizes\s*\(\s*(\d+)\s*\)\s*=\s*Real\s+([^\n!]+)", text, re.I)
    im = re.search(r"Timestep\s+Intervals\s*\(\s*(\d+)\s*\)\s*=\s*([^\n!]+)", text, re.I)
    if not sm or not im:
        fail(f"missing segmented time schedule in {sif_path}")
    sizes = [float(v) for v in sm.group(2).split()]
    counts = [int(v) for v in im.group(2).split()]
    if len(sizes) != len(counts) or len(sizes) != int(sm.group(1)) or len(counts) != int(im.group(1)):
        fail(f"inconsistent time schedule in {sif_path}")
    times, step, t = {}, 0, 0.0
    for dt, count in zip(sizes, counts):
        for _ in range(count):
            step += 1
            t += dt
            times[step] = t
    return times

def trapz(points):
    return sum((points[i][1] + points[i-1][1]) * 0.5 *
               (points[i][0] - points[i-1][0])
               for i in range(1, len(points)))

for gap in GAPS_MM:
    metrics = {}
    for divisions in DIVISIONS:
        case = ROOT / f"gap-{gap}mm" / f"n{divisions}"
        csv_path = case / "target_induced_current_summary.csv"
        sif_path = case / "islam-pi-pulse.sif"
        if not csv_path.is_file() or not sif_path.is_file():
            fail(f"missing output for gap={gap} mm, divisions={divisions}")
        times = read_times(sif_path)
        with csv_path.open(newline="") as f:
            data = list(csv.DictReader(f))
        if len(data) < 10:
            fail(f"insufficient time samples in {csv_path}")
        rms_points, integral_points = [], []
        for item in data:
            step = int(item["time_step"])
            if step not in times:
                fail(f"step {step} absent from SIF schedule in {sif_path}")
            rms = float(item["volume_weighted_rms_J_A_per_m2"])
            integral = float(item["integral_abs_J_dV_A"])
            if not math.isfinite(rms) or not math.isfinite(integral) or rms < 0 or integral < 0:
                fail(f"invalid response value in {csv_path}")
            rms_points.append((times[step], rms))
            integral_points.append((times[step], integral))
        rms_points.sort()
        integral_points.sort()
        metrics[divisions] = {
            "peak_rms": max(v for _, v in rms_points),
            "time_integral_rms": trapz(rms_points),
            "time_integral_absJdV": trapz(integral_points),
            "mesh_elements_lines": sum(1 for _ in (case / "mesh.elements").open()),
        }
    coarse, medium, fine = (metrics[d] for d in DIVISIONS)
    def rel(a, b):
        return abs(a-b) / abs(b) if b else math.inf
    errors = {
        "peak_rms_medium_to_fine": rel(medium["peak_rms"], fine["peak_rms"]),
        "time_integral_rms_medium_to_fine": rel(medium["time_integral_rms"], fine["time_integral_rms"]),
        "time_integral_absJdV_medium_to_fine": rel(medium["time_integral_absJdV"], fine["time_integral_absJdV"]),
    }
    converged = all(v < 0.05 for v in errors.values())
    for divisions in DIVISIONS:
        row = {"gap_mm": gap, "refinement_divisions": divisions, **metrics[divisions]}
        rows.append(row)
    rows.append({"gap_mm": gap, "refinement_divisions": "medium_vs_fine_relative_error",
                 **errors, "status": "CONVERGED<5%" if converged else "NOT_CONVERGED"})
    print(f"{gap} mm: n=3/5/8 peak RMS = " +
          " / ".join(f"{metrics[d]['peak_rms']:.8g}" for d in DIVISIONS))
    print(f"{gap} mm: medium-to-fine relative errors = " +
          ", ".join(f"{k}={v:.3%}" for k, v in errors.items()))
    print(f"{gap} mm: {'CONVERGED (<5% on all three metrics)' if converged else 'NOT CONVERGED (<5% criterion not met)'}")

out = ROOT / "mesh_convergence_summary.csv"
keys = sorted({k for row in rows for k in row})
with out.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=keys)
    writer.writeheader()
    writer.writerows(rows)
print(f"Saved mesh-convergence report: {out}")
print("NOTE: <5% is a declared numerical screening threshold, not proof of physical accuracy.")
