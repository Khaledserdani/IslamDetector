#!/usr/bin/env python3
"""Validate finite magnetic fields and reject post-pulse numerical runaway in Elmer VTU outputs."""
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

PULSE_CENTER_STEP = 20  # 200 us / 10 us
RUNAWAY_FACTOR = 10.0

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

steps = sorted(by_step)
if len(steps) < 2:
    raise SystemExit("FAIL: fewer than two distinct transient output steps")
series = [(step, max(by_step[step])) for step in steps]
summary = root / "magnetic_flux_density_summary.csv"
with summary.open("w") as f:
    f.write("time_step,max_B_magnitude\n")
    for step, value in series:
        f.write(f"{step},{value:.12g}\n")

if max(value for _, value in series) <= 0:
    raise SystemExit("FAIL: magnetic flux density is identically zero")

post_pulse = [(step, value) for step, value in series if step >= PULSE_CENTER_STEP]
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
