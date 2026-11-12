#!/usr/bin/env python3
"""Summarize target response across PI coil-to-target gaps using axisymmetric volume weighting."""
import csv
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: summarize_pi_target_gap_sweep.py SWEEP_ROOT")

root = Path(sys.argv[1])
gaps = (0.045, 0.075, 0.100, 0.150)
summary_rows = []

for gap in gaps:
    case_name = f"gap-{gap:.3f}".replace(".", "p")
    case_dir = root / case_name
    csv_path = case_dir / "target_induced_current_summary.csv"
    if not csv_path.is_file():
        raise SystemExit(f"FAIL: missing target-current CSV: {csv_path}")
    with csv_path.open(newline="") as handle:
        max_rows = {int(row["time_step"]): float(row["max_target_current_density_A_per_m2"])
                    for row in csv.DictReader(handle)}

    rms_by_step = {}
    mean_by_step = {}
    files = sorted(case_dir.glob("islam-pi-pulse_t*.vtu"))
    if len(files) != 40:
        raise SystemExit(f"FAIL: expected 40 VTU snapshots for {gap*1000:.0f} mm, found {len(files)}")

    for path in files:
        match = re.search(r"_t(\d+)\.vtu$", path.name)
        if not match:
            raise SystemExit(f"FAIL: invalid VTU timestep filename: {path.name}")
        step = int(match.group(1))
        tree = ET.parse(path)
        cell_data = next(tree.iter("CellData"), None)
        points_node = next(tree.iter("Points"), None)
        cells_node = next(tree.iter("Cells"), None)
        if cell_data is None or points_node is None or cells_node is None:
            raise SystemExit(f"FAIL: incomplete VTU mesh data in {path.name}")

        cell_arrays = {(a.attrib.get("Name") or "").strip().lower(): a
                       for a in cell_data.findall("DataArray")}
        cell_topology = {(a.attrib.get("Name") or "").strip().lower(): a
                         for a in cells_node.findall("DataArray")}
        point_array = next(points_node.findall("DataArray"), None)
        required = ("geometryids", "current density e")
        if any(name not in cell_arrays for name in required) or point_array is None:
            raise SystemExit(f"FAIL: target current or points missing in {path.name}")
        if any(name not in cell_topology for name in ("connectivity", "offsets", "types")):
            raise SystemExit(f"FAIL: cell topology missing in {path.name}")

        geometry_ids = [int(float(x)) for x in (cell_arrays["geometryids"].text or "").split()]
        current_array = cell_arrays["current density e"]
        components = int(current_array.attrib.get("NumberOfComponents", "1"))
        current_values = [float(x) for x in (current_array.text or "").split()]
        if components != 3 or len(current_values) != 3 * len(geometry_ids):
            raise SystemExit(f"FAIL: malformed current-density vectors in {path.name}")

        point_values = [float(x) for x in (point_array.text or "").split()]
        point_components = int(point_array.attrib.get("NumberOfComponents", "3"))
        if point_components != 3 or len(point_values) % 3:
            raise SystemExit(f"FAIL: malformed point coordinates in {path.name}")
        points = [tuple(point_values[i:i+3]) for i in range(0, len(point_values), 3)]

        connectivity = [int(x) for x in (cell_topology["connectivity"].text or "").split()]
        offsets = [int(x) for x in (cell_topology["offsets"].text or "").split()]
        types = [int(x) for x in (cell_topology["types"].text or "").split()]
        if len(offsets) != len(geometry_ids) or len(types) != len(geometry_ids):
            raise SystemExit(f"FAIL: cell topology count mismatch in {path.name}")
        if any(cell_type != 5 for cell_type in types):
            raise SystemExit(f"FAIL: expected triangular cells in {path.name}")
        if len(connectivity) != 3 * len(geometry_ids):
            raise SystemExit(f"FAIL: malformed triangle connectivity in {path.name}")

        weighted_j2 = 0.0
        weighted_j = 0.0
        total_weight = 0.0
        for index, geometry_id in enumerate(geometry_ids):
            if geometry_id != 3:
                continue
            ids = connectivity[3*index:3*index+3]
            p0, p1, p2 = (points[node] for node in ids)
            u = (p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2])
            v = (p2[0]-p0[0], p2[1]-p0[1], p2[2]-p0[2])
            cross = (u[1]*v[2]-u[2]*v[1],
                     u[2]*v[0]-u[0]*v[2],
                     u[0]*v[1]-u[1]*v[0])
            area = 0.5 * math.sqrt(sum(value*value for value in cross))
            radius = max(0.0, (p0[0]+p1[0]+p2[0]) / 3.0)
            weight = 2.0 * math.pi * radius * area
            jx, jy, jz = current_values[3*index:3*index+3]
            magnitude = math.sqrt(jx*jx + jy*jy + jz*jz)
            weighted_j2 += weight * magnitude * magnitude
            weighted_j += weight * magnitude
            total_weight += weight

        if total_weight <= 0:
            raise SystemExit(f"FAIL: no positive axisymmetric target volume in {path.name}")
        rms_by_step[step] = math.sqrt(weighted_j2 / total_weight)
        mean_by_step[step] = weighted_j / total_weight

    if set(rms_by_step) != set(max_rows):
        raise SystemExit(f"FAIL: VTU and max-current timestep sets differ for {gap*1000:.0f} mm")
    peak_step = max(rms_by_step, key=rms_by_step.get)
    final_step = max(rms_by_step)
    peak_rms = rms_by_step[peak_step]
    final_rms = rms_by_step[final_step]
    peak_max = max(max_rows.values())
    final_max = max_rows[final_step]
    if peak_rms <= 0 or final_rms >= peak_rms * 0.10:
        raise SystemExit(f"FAIL: axisymmetric RMS target current did not decay at {gap*1000:.0f} mm")

    case_summary = case_dir / "target_current_axisymmetric_summary.csv"
    with case_summary.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_step", "max_target_current_density_A_per_m2",
                         "rms_target_current_density_A_per_m2",
                         "mean_target_current_density_A_per_m2"])
        for step in sorted(rms_by_step):
            writer.writerow([step, f"{max_rows[step]:.12g}",
                             f"{rms_by_step[step]:.12g}", f"{mean_by_step[step]:.12g}"])

    summary_rows.append({
        "target_gap_mm": f"{gap*1000:.0f}",
        "rms_peak_step": peak_step,
        "peak_rms_target_current_density_A_per_m2": f"{peak_rms:.12g}",
        "peak_max_target_current_density_A_per_m2": f"{peak_max:.12g}",
        "final_rms_target_current_density_A_per_m2": f"{final_rms:.12g}",
        "final_to_peak_rms_ratio": f"{final_rms/peak_rms:.8g}",
        "final_max_target_current_density_A_per_m2": f"{final_max:.12g}",
    })

summary_path = root / "pi_target_gap_sweep_summary.csv"
with summary_path.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
    writer.writeheader()
    writer.writerows(summary_rows)

print(f"PASS: axisymmetric volume-weighted target-current summary saved to {summary_path}")
for row in summary_rows:
    print(f"{row['target_gap_mm']} mm: peak RMS J={row['peak_rms_target_current_density_A_per_m2']} A/m^2")
