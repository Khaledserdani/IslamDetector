#!/usr/bin/env python3
"""Validate finite, time-varying magnetic-flux-density fields in Elmer VTU outputs."""
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: verify_pi_pulse_vtu.py OUTPUT_DIRECTORY")

root = Path(sys.argv[1])
files = sorted(root.glob("islam-pi-pulse*.vtu"))
if len(files) < 2:
    raise SystemExit("FAIL: fewer than two transient VTU snapshots")

by_step = defaultdict(list)
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
        if name.strip().lower() not in ("magnetic flux density", "b"):
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

steps = sorted(by_step)
if len(steps) < 2:
    raise SystemExit("FAIL: fewer than two distinct transient output steps")
series = [(step, max(by_step[step])) for step in steps]
peak_step, peak_value = max(series, key=lambda item: item[1])
first_value = series[0][1]
last_value = series[-1][1]
if peak_value <= 0:
    raise SystemExit("FAIL: magnetic flux density is identically zero")
if peak_step == steps[0] or peak_step == steps[-1]:
    raise SystemExit("FAIL: pulse response peak was not bracketed by earlier and later outputs")
if peak_value <= first_value * 1.05 or peak_value <= last_value * 1.05:
    raise SystemExit("FAIL: magnetic response does not rise and decay around the pulse")

summary = root / "magnetic_flux_density_summary.csv"
with summary.open("w") as f:
    f.write("time_step,max_B_magnitude\n")
    for step, value in series:
        f.write(f"{step},{value:.12g}\n")

print(f"VTU snapshots = {len(files)} across {len(steps)} time steps")
print(f"Max |B| peak  = {peak_value:.9g} at output step {peak_step}")
print(f"First |B|     = {first_value:.9g}; final |B| = {last_value:.9g}")
print("PASS: all B vectors are finite and the pulse response rises then decays")
