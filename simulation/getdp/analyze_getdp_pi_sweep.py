#!/usr/bin/env python3
"""Parse GetDP TimeTable output and summarize target eddy-current density."""
from __future__ import annotations
import csv
import math
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
TARGET_VOLUME_M3 = math.pi * 0.250**2 * 0.005
NUMBER = re.compile(r"[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eEdD][-+]?[0-9]+)?")

def numbers(line: str):
    return [float(x.replace("D", "E").replace("d", "e")) for x in NUMBER.findall(line)]

def read_table(path: Path):
    rows = []
    for line in path.read_text(errors="replace").splitlines():
        vals = numbers(line)
        if len(vals) >= 2:
            # GetDP TimeTable convention: first numeric column is time, last is value.
            t_candidates = [x for x in vals[:-1] if -1e-12 <= x <= 400.001e-6]
            if t_candidates:
                rows.append((t_candidates[0], vals[-1]))
        elif len(vals) == 1:
            # Some GetDP builds emit a scalar per line; infer the fixed 1 us step index.
            rows.append((len(rows) * 1e-6, vals[0]))
    by_time = {}
    for t, q in rows:
        if math.isfinite(t) and math.isfinite(q) and 0 <= t <= 400.001e-6 and q >= 0:
            by_time[t] = q
    out = sorted(by_time.items())
    if len(out) < 20:
        preview = path.read_text(errors="replace")[:2500]
        raise SystemExit(f"Insufficient GetDP J2 time samples in {path}: {len(out)}. Preview:\\n{preview}")
    return out

summary = []
for gap_mm in (45, 75, 100, 150):
    folder = ROOT / f"gap-{gap_mm}mm"
    data = read_table(folder / "j2.txt")
    rms = [(t, math.sqrt(q / TARGET_VOLUME_M3)) for t, q in data]
    peak_t, peak = max(rms, key=lambda x: x[1])
    at_150 = min(rms, key=lambda x: abs(x[0] - 150e-6))[1]
    final_t, final = rms[-1]
    summary.append({
        "gap_mm": gap_mm,
        "samples": len(rms),
        "peak_time_us": peak_t * 1e6,
        "peak_volume_rms_J_A_per_m2": peak,
        "J_rms_at_150us_A_per_m2": at_150,
        "J_rms_at_final_time_A_per_m2": final,
        "final_time_us": final_t * 1e6,
        "source": "GetDP transient FEM; axisymmetric; imposed 20 A-turn smooth pulse",
    })

out_csv = ROOT / "getdp_pi_target_gap_sweep.csv"
with out_csv.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(summary[0]))
    w.writeheader()
    w.writerows(summary)
print("GETDP_PI_TARGET_GAP_SWEEP")
for row in summary:
    print(row)
print(f"WROTE {out_csv}")
