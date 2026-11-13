#!/usr/bin/env python3
"""Summarize GetDP mesh convergence at the 45 mm PI target gap."""
from __future__ import annotations
import csv
import math
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
TARGET_VOLUME_M3 = math.pi * 0.250**2 * 0.005
NUMBER = re.compile(r"[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eEdD][-+]?[0-9]+)?")

def read_j2(path: Path):
    values = []
    for line in path.read_text(errors="replace").splitlines():
        nums = [float(x.replace("D", "E").replace("d", "e")) for x in NUMBER.findall(line)]
        if len(nums) >= 2:
            t_candidates = [x for x in nums[:-1] if -1e-12 <= x <= 400.001e-6]
            if t_candidates:
                values.append((t_candidates[0], nums[-1]))
    by_time = {t:q for t,q in values if math.isfinite(t) and math.isfinite(q) and q >= 0}
    rows = sorted(by_time.items())
    if len(rows) < 390:
        raise SystemExit(f"Expected at least 390 J2 samples in {path}; got {len(rows)}")
    return rows

records = []
for divisions in (3,4,6):
    folder = ROOT / f"gap-45mm-refine-{divisions}"
    data = read_j2(folder / "j2.txt")
    rms = [(t, math.sqrt(q / TARGET_VOLUME_M3)) for t,q in data]
    peak_t, peak = max(rms, key=lambda x:x[1])
    at_150 = min(rms, key=lambda x:abs(x[0]-150e-6))
    at_400 = min(rms, key=lambda x:abs(x[0]-400e-6))
    mesh_log = (folder / "gmsh.log").read_text(errors="replace")
    nodes = re.findall(r"Nodes\s*:\s*(\d+)", mesh_log)
    elements = re.findall(r"Elements\s*:\s*(\d+)", mesh_log)
    records.append({
        "gap_mm":45,
        "target_thickness_divisions":divisions,
        "samples":len(rms),
        "peak_time_us":peak_t*1e6,
        "peak_volume_rms_J_A_per_m2":peak,
        "J_rms_at_150us_A_per_m2":at_150[1],
        "J_rms_at_400us_A_per_m2":at_400[1],
        "gmsh_nodes_reported":nodes[-1] if nodes else "",
        "gmsh_elements_reported":elements[-1] if elements else "",
        "relative_peak_change_vs_previous_percent":"",
    })
for i in range(1,len(records)):
    prev,cur=records[i-1],records[i]
    cur["relative_peak_change_vs_previous_percent"]=abs(cur["peak_volume_rms_J_A_per_m2"]/prev["peak_volume_rms_J_A_per_m2"]-1)*100
out=ROOT/"getdp_mesh_convergence_45mm.csv"
with out.open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(records[0]))
    w.writeheader(); w.writerows(records)
print("GETDP_MESH_CONVERGENCE_45MM")
for r in records:
    print(r)
print(f"WROTE {out}")
print("Acceptance remains open: compare successive mesh changes; no convergence claim is made automatically.")
