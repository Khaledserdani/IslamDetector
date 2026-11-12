#!/usr/bin/env python3
"""Verify the matched PI transmitter control with the conductive target removed."""
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: verify_pi_pulse_no_target_vtu.py OUTPUT_DIRECTORY")
root = Path(sys.argv[1])
files = sorted(root.glob("islam-pi-pulse*.vtu"))
if len(files) < 2:
    raise SystemExit("FAIL: fewer than two no-target transient VTU snapshots")

series = []
for path in files:
    match = re.search(r"_t(\d+)\.vtu$", path.name)
    if not match:
        raise SystemExit(f"FAIL: timestep suffix missing from {path.name}")
    step = int(match.group(1))
    tree = ET.parse(path)
    b_values = None
    names = []
    for array in tree.iter("DataArray"):
        name = (array.attrib.get("Name") or "").strip()
        names.append(name)
        if name.lower() in ("magnetic flux density", "b"):
            components = int(array.attrib.get("NumberOfComponents", "1"))
            if components not in (2, 3):
                continue
            values = [float(x) for x in (array.text or "").split()]
            if not values or len(values) % components:
                raise SystemExit(f"FAIL: malformed B vector in {path.name}")
            if not all(math.isfinite(x) for x in values):
                raise SystemExit(f"FAIL: non-finite B in {path.name}")
            b_values = [
                math.sqrt(sum(values[i+j]**2 for j in range(components)))
                for i in range(0, len(values), components)
            ]
    if b_values is None:
        raise SystemExit(f"FAIL: B field missing from {path.name}; arrays={names}")

    cell_data = next(tree.iter("CellData"), None)
    if cell_data is None:
        raise SystemExit(f"FAIL: CellData missing from {path.name}")
    arrays = {(a.attrib.get("Name") or "").strip().lower(): a for a in cell_data.findall("DataArray")}
    if "geometryids" not in arrays:
        raise SystemExit(f"FAIL: GeometryIds missing from {path.name}")
    geometry_ids = [int(float(x)) for x in (arrays["geometryids"].text or "").split()]
    if 3 in geometry_ids:
        raise SystemExit(f"FAIL: target body still exists in no-target control {path.name}")
    if not b_values:
        raise SystemExit(f"FAIL: empty transmitter magnetic-field array in {path.name}")
    series.append((step, max(b_values)))

series.sort()
if not any(value > 0 for _, value in series):
    raise SystemExit("FAIL: transmitter magnetic field is zero in every no-target snapshot")
if len({step for step, _ in series}) != len(series):
    raise SystemExit("FAIL: duplicate transient time steps")
out = root / "no_target_magnetic_flux_density_summary.csv"
with out.open("w") as f:
    f.write("time_step,max_B_magnitude\n")
    for step, value in series:
        f.write(f"{step},{value:.12g}\n")
print(f"No-target VTU snapshots = {len(series)}")
print(f"No-target peak |B| = {max(v for _, v in series):.9g}")
print(f"Final no-target |B| = {series[-1][1]:.9g}")
print("PASS: transmitter field is present and Aluminium_Target cells are absent")
