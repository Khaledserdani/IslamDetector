#!/usr/bin/env python3
"""Validate finite magnetic fields and reject post-pulse numerical runaway in Elmer VTU outputs."""
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

PULSE_START_TIME = 50e-6
POST_PULSE_START_TIME = 175e-6  # 25 us after transmitter turn-off
RUNAWAY_FACTOR = 10.0

if len(sys.argv) != 2:
    raise SystemExit("usage: verify_pi_pulse_vtu.py OUTPUT_DIRECTORY")

root = Path(sys.argv[1])
sif_path = root / "islam-pi-pulse.sif"
if not sif_path.is_file():
    raise SystemExit("FAIL: copied SIF is required to map VTU steps to physical time")
sif_text = sif_path.read_text(encoding="utf-8")
sizes_match = re.search(r"Timestep\s+Sizes\s*\(\s*(\d+)\s*\)\s*=\s*Real\s+([^\n!]+)", sif_text, re.I)
intervals_match = re.search(r"Timestep\s+Intervals\s*\(\s*(\d+)\s*\)\s*=\s*([^\n!]+)", sif_text, re.I)
if not sizes_match or not intervals_match:
    raise SystemExit("FAIL: could not read segmented time-step schedule from SIF")
time_sizes = [float(x) for x in sizes_match.group(2).split()]
time_intervals = [int(x) for x in intervals_match.group(2).split()]
if len(time_sizes) != len(time_intervals) or len(time_sizes) != int(sizes_match.group(1)) or len(time_intervals) != int(intervals_match.group(1)):
    raise SystemExit("FAIL: inconsistent SIF time-step vectors")
time_by_step = {}
step_cursor = 0
elapsed = 0.0
for dt, count in zip(time_sizes, time_intervals):
    for _ in range(count):
        elapsed += dt
        step_cursor += 1
        time_by_step[step_cursor] = elapsed
files = sorted(root.glob("islam-pi-pulse*.vtu"))
if len(files) < 2:
    raise SystemExit("FAIL: fewer than two transient VTU snapshots")

def axisymmetric_cell_volumes(vtu_tree, expected_cells):
    points_node = next(vtu_tree.iter("Points"), None)
    cells_node = next(vtu_tree.iter("Cells"), None)
    if points_node is None or cells_node is None:
        raise ValueError("VTU Points/Cells missing")
    point_array = points_node.find("DataArray")
    if point_array is None:
        raise ValueError("VTU point coordinates missing")
    coords = [float(x) for x in (point_array.text or "").split()]
    ncomp = int(point_array.attrib.get("NumberOfComponents", "3"))
    if ncomp < 2 or len(coords) % ncomp:
        raise ValueError("malformed VTU point coordinates")
    points = [(coords[i], coords[i+1]) for i in range(0, len(coords), ncomp)]
    cell_arrays = {(a.attrib.get("Name") or "").lower(): a for a in cells_node.findall("DataArray")}
    if not {"connectivity", "offsets"}.issubset(cell_arrays):
        raise ValueError("VTU connectivity/offsets missing")
    connectivity = [int(x) for x in (cell_arrays["connectivity"].text or "").split()]
    offsets = [int(x) for x in (cell_arrays["offsets"].text or "").split()]
    if len(offsets) != expected_cells:
        raise ValueError("VTU cell count does not match GeometryIds")
    volumes, start = [], 0
    for end in offsets:
        ids = connectivity[start:end]
        start = end
        if len(ids) < 3 or any(i < 0 or i >= len(points) for i in ids):
            raise ValueError("invalid cell connectivity")
        # Polygon area and centroid in the axisymmetric (r,z) plane.
        twice_area = cx = cy = 0.0
        for k, idx in enumerate(ids):
            x1, y1 = points[idx]
            x2, y2 = points[ids[(k+1) % len(ids)]]
            cross = x1*y2 - x2*y1
            twice_area += cross
            cx += (x1+x2)*cross
            cy += (y1+y2)*cross
        if abs(twice_area) < 1e-24:
            raise ValueError("zero-area mesh cell")
        area = abs(twice_area) / 2.0
        centroid_r = (cx / (3.0*twice_area))
        # Revolve the 2-D cell around the symmetry axis: V = 2*pi*r_centroid*A.
        volumes.append(2.0*math.pi*max(centroid_r, 0.0)*area)
    return volumes


by_step = defaultdict(list)
target_current_by_step = {}
target_integral_by_step = {}
target_rms_by_step = {}
for path in files:
    match = re.search(r"_t(\d+)\.vtu$", path.name)
    if not match:
        raise SystemExit(f"FAIL: VTU filename has no timestep suffix: {path.name}")
    step = int(match.group(1))
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        lines = path.read_bytes().splitlines()
        bad_line = exc.position[0] - 1 if exc.position else -1
        context = lines[bad_line][:240] if 0 <= bad_line < len(lines) else b"<line unavailable>"
        prefix = path.read_bytes()[:240]
        raise SystemExit(
            f"FAIL: could not parse VTU {path.name}: {exc}; "
            f"offending_line={context!r}; file_prefix={prefix!r}"
        )
    found = False
    available_names = []
    for array in tree.iter("DataArray"):
        name = (array.attrib.get("Name") or "").strip()
        if name:
            available_names.append(name)
        if name.lower() not in ("magnetic flux density", "b"):
            continue
        components = int(array.attrib.get("NumberOfComponents", "1"))
        if components not in (2, 3):
            continue
        values = [float(x) for x in (array.text or "").split()]
        if not values or len(values) % components:
            raise SystemExit(f"FAIL: malformed magnetic-flux-density vector in {path.name}")
        if not all(math.isfinite(x) for x in values):
            raise SystemExit(f"FAIL: non-finite magnetic-flux-density value in {path.name}")
        magnitudes = [
            math.sqrt(sum(values[i+j]**2 for j in range(components)))
            for i in range(0, len(values), components)
        ]
        by_step[step].append(max(magnitudes))
        found = True
    if not found:
        names = ", ".join(sorted(set(available_names))) or "<none>"
        raise SystemExit(f"FAIL: magnetic flux density array missing from {path.name}; available arrays: {names}")

    # GeometryIds 3 is the separately meshed Aluminium_Target physical body.
    cell_data = next(tree.iter("CellData"), None)
    if cell_data is None:
        raise SystemExit(f"FAIL: CellData missing from {path.name}")
    cell_arrays = {
        (a.attrib.get("Name") or "").strip().lower(): a
        for a in cell_data.findall("DataArray")
    }
    if "geometryids" not in cell_arrays or "current density e" not in cell_arrays:
        raise SystemExit(f"FAIL: GeometryIds/current density e missing from {path.name}")
    geometry_ids = [int(float(x)) for x in (cell_arrays["geometryids"].text or "").split()]
    current_array = cell_arrays["current density e"]
    current_components = int(current_array.attrib.get("NumberOfComponents", "1"))
    current_values = [float(x) for x in (current_array.text or "").split()]
    if current_components != 3 or len(current_values) != 3 * len(geometry_ids):
        raise SystemExit(f"FAIL: malformed cell current-density vectors in {path.name}")
    if not all(math.isfinite(x) for x in current_values):
        raise SystemExit(f"FAIL: non-finite cell current density in {path.name}")
    target_magnitudes = [
        math.sqrt(sum(current_values[3*i+j]**2 for j in range(3)))
        for i, geometry_id in enumerate(geometry_ids)
        if geometry_id == 3
    ]
    if not target_magnitudes:
        raise SystemExit(f"FAIL: no Aluminium_Target cells (GeometryIds=3) in {path.name}")
    target_current_by_step[step] = max(target_magnitudes)
    try:
        cell_volumes = axisymmetric_cell_volumes(tree, len(geometry_ids))
    except ValueError as exc:
        raise SystemExit(f"FAIL: cannot integrate axisymmetric target volume in {path.name}: {exc}")
    target_integral = sum(
        math.sqrt(sum(current_values[3*i+j]**2 for j in range(3))) * cell_volumes[i]
        for i, geometry_id in enumerate(geometry_ids) if geometry_id == 3
    )
    target_rms = math.sqrt(
        sum((math.sqrt(sum(current_values[3*i+j]**2 for j in range(3)))**2) * cell_volumes[i]
            for i, geometry_id in enumerate(geometry_ids) if geometry_id == 3)
        / sum(cell_volumes[i] for i, geometry_id in enumerate(geometry_ids) if geometry_id == 3)
    )
    target_integral_by_step[step] = target_integral
    target_rms_by_step[step] = target_rms

steps = sorted(by_step)
if len(steps) < 2:
    raise SystemExit("FAIL: fewer than two distinct transient output steps")
series = [(step, max(by_step[step])) for step in steps]
summary = root / "magnetic_flux_density_summary.csv"
with summary.open("w") as f:
    f.write("time_step,max_B_magnitude\n")
    for step, value in series:
        f.write(f"{step},{value:.12g}\n")

target_summary = root / "target_induced_current_summary.csv"
with target_summary.open("w") as f:
    f.write("time_step,max_target_current_density_A_per_m2,integral_abs_J_dV_A,volume_weighted_rms_J_A_per_m2\n")
    for step in steps:
        f.write(f"{step},{target_current_by_step[step]:.12g},{target_integral_by_step[step]:.12g},{target_rms_by_step[step]:.12g}\n")

if max(value for _, value in series) <= 0:
    raise SystemExit("FAIL: magnetic flux density is identically zero")

post_pulse = [(step, value) for step, value in series if time_by_step.get(step, -1.0) >= POST_PULSE_START_TIME]
if len(post_pulse) < 6:
    raise SystemExit("FAIL: insufficient post-pulse snapshots to assess decay")
minimum_step, minimum_value = min(post_pulse, key=lambda item: item[1])
last_step, last_value = post_pulse[-1]
tail = [value for _, value in post_pulse[-5:]]
if minimum_value > 0 and last_value >= minimum_value * RUNAWAY_FACTOR and all(
    tail[i] < tail[i + 1] for i in range(len(tail) - 1)
):
    growth = last_value / minimum_value
    raise SystemExit(
        f"FAIL: post-pulse numerical runaway detected; "
        f"minimum |B|={minimum_value:.9g} at step {minimum_step}, "
        f"final |B|={last_value:.9g} at step {last_step}, "
        f"growth factor={growth:.6g}; summary saved to {summary}"
    )

pulse_peak_step, pulse_peak = max(post_pulse, key=lambda item: item[1])
if pulse_peak <= minimum_value * 1.05 or pulse_peak <= last_value * 1.05:
    raise SystemExit(
        f"FAIL: post-pulse response does not show a bounded rise and decay; "
        f"peak={pulse_peak:.9g} at step {pulse_peak_step}, "
        f"post-pulse minimum={minimum_value:.9g}, final={last_value:.9g}; "
        f"summary saved to {summary}"
    )

print(f"VTU snapshots = {len(files)} across {len(steps)} time steps")
print(f"Post-pulse |B| peak = {pulse_peak:.9g} at step {pulse_peak_step}")
print(f"Post-pulse minimum = {minimum_value:.9g}; final = {last_value:.9g}")
print("PASS: finite magnetic field with bounded post-pulse decay")

target_series = [(step, target_current_by_step[step]) for step in steps]
target_peak_step, target_peak = max(target_series, key=lambda item: item[1])
target_final_step, target_final = target_series[-1]
if target_peak <= 0:
    raise SystemExit("FAIL: no induced current detected in Aluminium_Target")
if time_by_step.get(target_peak_step, 0.0) < PULSE_START_TIME:
    raise SystemExit(
        f"FAIL: target-current peak precedes the transmitter pulse; "
        f"peak={target_peak:.9g} at step {target_peak_step}"
    )
if target_final >= target_peak * 0.10:
    raise SystemExit(
        f"FAIL: induced target current did not decay sufficiently; "
        f"peak={target_peak:.9g} at step {target_peak_step}, "
        f"final={target_final:.9g} at step {target_final_step}"
    )
print(f"Target induced-current peak = {target_peak:.9g} A/m^2 at step {target_peak_step}")
print(f"Target induced-current final = {target_final:.9g} A/m^2 at step {target_final_step}")
print(f"Peak volume-integrated |J| dV = {max(target_integral_by_step.values()):.9g} A")
print(f"Peak volume-weighted RMS |J| = {max(target_rms_by_step.values()):.9g} A/m^2")
print("NOTE: integral |J| dV is a scalar response proxy, not net loop current or receiver voltage.")
print(f"Peak volume-integrated |J| dV = {max(target_integral_by_step.values()):.9g} A")
print(f"Peak volume-weighted RMS |J| = {max(target_rms_by_step.values()):.9g} A/m^2")
print("NOTE: integral |J| dV is a scalar response proxy, not net loop current or receiver voltage.")
print("PASS: nonzero induced current in the separate aluminium target with post-pulse decay")
