#!/usr/bin/env python3
"""Compare GetDP and Elmer target-current RMS on matched axisymmetric PI cases."""
from __future__ import annotations
import csv
import math
import re
import sys
from pathlib import Path

GETDP_CSV = Path(sys.argv[1])
ELMER_ROOT = Path(sys.argv[2])

def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))

def time_map(sif_path):
    text = sif_path.read_text(encoding="utf-8")
    sm = re.search(r"Timestep\s+Sizes\s*\(\s*(\d+)\s*\)\s*=\s*Real\s+([^\n!]+)", text, re.I)
    im = re.search(r"Timestep\s+Intervals\s*\(\s*(\d+)\s*\)\s*=\s*([^\n!]+)", text, re.I)
    if not sm or not im:
        raise SystemExit(f"Missing timestep schedule: {sif_path}")
    sizes = [float(x) for x in sm.group(2).split()]
    counts = [int(x) for x in im.group(2).split()]
    if len(sizes) != int(sm.group(1)) or len(counts) != int(im.group(1)) or len(sizes) != len(counts):
        raise SystemExit(f"Malformed timestep schedule: {sif_path}")
    out, step, t = {}, 0, 0.0
    for dt, n in zip(sizes, counts):
        for _ in range(n):
            step += 1
            t += dt
            out[step] = t
    return out

getdp = {int(r["gap_mm"]): r for r in read_csv(GETDP_CSV)}
rows = []
for gap in (45, 75, 100, 150):
    case = ELMER_ROOT / f"gap-{gap/1000:.3f}".replace(".", "p")
    csv_path = case / "target_current_axisymmetric_summary.csv"
    sif_path = case / "islam-pi-pulse.sif"
    if not csv_path.is_file() or not sif_path.is_file():
        raise SystemExit(f"Missing Elmer summary/SIF for {gap} mm")
    times = time_map(sif_path)
    data = read_csv(csv_path)
    by_time = {}
    for r in data:
        step = int(r["time_step"])
        if step not in times:
            raise SystemExit(f"Elmer timestep {step} absent from SIF time schedule")
        t_us = times[step] * 1e6
        j = float(r["rms_target_current_density_A_per_m2"])
        if not math.isfinite(j) or j < 0:
            raise SystemExit(f"Invalid Elmer RMS current density at {gap} mm, step {step}")
        by_time[round(t_us, 6)] = j
    if len(by_time) < 200:
        raise SystemExit(f"Insufficient Elmer time samples at {gap} mm: {len(by_time)}")
    peak_t, peak = max(by_time.items(), key=lambda item: item[1])
    samples = {}
    for target_t in (150.0, 400.0):
        nearest = min(by_time, key=lambda t: abs(t-target_t))
        if abs(nearest-target_t) > 1e-5:
            raise SystemExit(f"Elmer does not contain exact {target_t} us sample at {gap} mm")
        samples[target_t] = by_time[nearest]
    g = getdp[gap]
    g_peak = float(g["peak_volume_rms_J_A_per_m2"])
    g_150 = float(g["J_rms_at_150us_A_per_m2"])
    g_400 = float(g["J_rms_at_final_time_A_per_m2"])
    rel = lambda a,b: abs(a-b)/abs(b)*100 if b else math.nan
    rows.append({
        "gap_mm": gap,
        "getdp_samples": int(g["samples"]),
        "elmer_samples": len(by_time),
        "getdp_peak_time_us": float(g["peak_time_us"]),
        "elmer_peak_time_us": peak_t,
        "getdp_peak_rms_J_A_per_m2": g_peak,
        "elmer_peak_rms_J_A_per_m2": peak,
        "peak_relative_difference_percent": rel(peak,g_peak),
        "getdp_J_rms_at_150us_A_per_m2": g_150,
        "elmer_J_rms_at_150us_A_per_m2": samples[150.0],
        "relative_difference_at_150us_percent": rel(samples[150.0],g_150),
        "getdp_J_rms_at_400us_A_per_m2": g_400,
        "elmer_J_rms_at_400us_A_per_m2": samples[400.0],
        "relative_difference_at_400us_percent": rel(samples[400.0],g_400),
        "evidence_class": "simulated cross-solver comparison; not hardware measurement",
    })

out = ELMER_ROOT / "getdp_elmer_gap_crosscheck.csv"
with out.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print("GETDP_ELMER_GAP_CROSSCHECK")
for r in rows:
    print(f"{r['gap_mm']} mm: peak GetDP={r['getdp_peak_rms_J_A_per_m2']:.6g}, "
          f"Elmer={r['elmer_peak_rms_J_A_per_m2']:.6g} A/m^2, "
          f"relative difference={r['peak_relative_difference_percent']:.2f}%")
print(f"WROTE {out}")
print("NOTE: This is a numerical cross-solver comparison. Agreement does not establish hardware accuracy.")
