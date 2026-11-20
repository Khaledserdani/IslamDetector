#!/usr/bin/env python3
"""Check that the zero-current Elmer control remains finite and near zero."""
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
LIMIT_T = 1.0e-9
if len(sys.argv) != 2:
    raise SystemExit("usage: verify_pi_zero_baseline.py OUTPUT_DIRECTORY")
root = Path(sys.argv[1])
files = sorted(root.glob("islam-pi-zero*.vtu"))
if len(files) < 2:
    raise SystemExit("FAIL: fewer than two zero-excitation VTU snapshots")
series = []
for path in files:
    match = re.search(r"_t(\d+)\.vtu$", path.name)
    if not match:
        raise SystemExit(f"FAIL: VTU filename has no timestep suffix: {path.name}")
    tree = ET.parse(path)
    arrays = [a for a in tree.iter("DataArray")
              if (a.attrib.get("Name") or "").strip().lower() in ("magnetic flux density", "b")]
    if not arrays:
        raise SystemExit(f"FAIL: magnetic flux density missing from {path.name}")
    maximum = 0.0
    for array in arrays:
        components = int(array.attrib.get("NumberOfComponents", "1"))
        if components not in (2, 3):
            continue
        values = [float(v) for v in (array.text or "").split()]
        if not values or len(values) % components:
            raise SystemExit(f"FAIL: malformed magnetic field in {path.name}")
        if not all(math.isfinite(v) for v in values):
            raise SystemExit(f"FAIL: non-finite magnetic field in {path.name}")
        for i in range(0, len(values), components):
            maximum = max(maximum, math.sqrt(sum(values[i+j] ** 2 for j in range(components))))
    series.append((int(match.group(1)), maximum))
series.sort()
with (root / "zero_baseline_summary.csv").open("w") as f:
    f.write("time_step,max_B_magnitude_T\n")
    for step, value in series:
        f.write(f"{step},{value:.12g}\n")
peak = max(value for _, value in series)
if peak > LIMIT_T:
    raise SystemExit(f"FAIL: zero-current control exceeded tolerance: max |B|={peak:.9g} T (limit {LIMIT_T:.1e} T)")
print(f"VTU snapshots = {len(files)}")
print(f"Maximum |B| over all zero-current snapshots = {peak:.9g} T")
print(f"PASS: zero-current baseline stayed below {LIMIT_T:.1e} T")
