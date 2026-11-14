#!/usr/bin/env python3
"""Static dimensional and excitation checks for the ISLAM LAB PI Elmer model.

This does not run Elmer or certify the transient solution. It checks that the
SIF excitation, homogenized TX winding geometry, and stated ampere-turn value
remain mutually consistent before an expensive FEM run.
"""
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIF = ROOT / "simulation/elmer/pi_pulse_separate_coil.sif"
GEO = ROOT / "simulation/elmer/pi_pulse_separate_coil.geo"

def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")

sif = SIF.read_text(encoding="utf-8")
geo = GEO.read_text(encoding="utf-8")

source_match = re.search(
    r'Current\s+Density\s*=\s*Variable\s+time\s+Real\s+LUA\s+"([^"]+)"',
    sif,
    flags=re.IGNORECASE | re.DOTALL,
)
if not source_match:
    fail("time-dependent LUA Current Density source not found in SIF")

expr = source_match.group(1)
pulse_match = re.fullmatch(
    r'\s*([0-9.eE+-]+)\s*\*\s*\(\s*'
    r'math\.tanh\(\(tx\[0\]\s*-\s*([0-9.eE+-]+)\)\s*/\s*([0-9.eE+-]+)\)\s*-\s*'
    r'math\.tanh\(\(tx\[0\]\s*-\s*([0-9.eE+-]+)\)\s*/\s*([0-9.eE+-]+)\)\s*\)\s*',
    expr,
)
if not pulse_match:
    fail(f"unsupported or changed pulse expression: {expr}")

coefficient, start, rise_width, end, fall_width = map(float, pulse_match.groups())
if not (0 < start < end and rise_width > 0 and fall_width > 0 and coefficient > 0):
    fail("pulse timing/coefficient values must be positive and ordered")
if not math.isclose(start, 50e-6, rel_tol=0, abs_tol=1e-12):
    fail(f"unexpected pulse start: {start:g} s")
if not math.isclose(end, 150e-6, rel_tol=0, abs_tol=1e-12):
    fail(f"unexpected pulse end: {end:g} s")
if not math.isclose(rise_width, 5e-6, rel_tol=0, abs_tol=1e-12):
    fail(f"unexpected rise smoothing: {rise_width:g} s")
if not math.isclose(fall_width, 5e-6, rel_tol=0, abs_tol=1e-12):
    fail(f"unexpected fall smoothing: {fall_width:g} s")

# Resolve the smoothed pulse edges rather than sampling them with a coarse step.
sizes_match = re.search(
    r"Timestep\s+Sizes\s*\(\s*(\d+)\s*\)\s*=\s*Real\s+([^\n!]+)",
    sif,
    flags=re.IGNORECASE,
)
intervals_match = re.search(
    r"Timestep\s+Intervals\s*\(\s*(\d+)\s*\)\s*=\s*([^\n!]+)",
    sif,
    flags=re.IGNORECASE,
)
if not sizes_match or not intervals_match:
    fail("segmented Timestep Sizes/Intervals definitions not found")
sizes = [float(x) for x in sizes_match.group(2).split()]
intervals = [int(x) for x in intervals_match.group(2).split()]
if int(sizes_match.group(1)) != len(sizes) or int(intervals_match.group(1)) != len(intervals) or len(sizes) != len(intervals):
    fail("Timestep Sizes/Intervals vector lengths do not match")
if any(x <= 0 for x in sizes) or any(x <= 0 for x in intervals):
    fail("time-step sizes and intervals must be positive")
time_cursor = 0.0
pulse_window_start = start - 3.0 * max(rise_width, fall_width)
pulse_window_end = end + 3.0 * max(rise_width, fall_width)
for dt, count in zip(sizes, intervals):
    segment_end = time_cursor + dt * count
    if segment_end > pulse_window_start and time_cursor < pulse_window_end:
        if dt > min(rise_width, fall_width) / 5.0 * (1.0 + 1e-9):
            fail(f"time step {dt:g} s is too coarse around pulse edges; require <= {min(rise_width, fall_width)/5.0:g} s")
    time_cursor = segment_end
if time_cursor < 1.0e-3 - 1e-12:
    fail(f"simulation horizon too short: {time_cursor:g} s; require at least 1 ms")

# The TX radial position and width are controlled Gmsh parameters.
inner_match = re.search(r'CoilInnerRadiusM\s*=\s*([0-9.eE+-]+)', geo)
width_match = re.search(r'CoilRadialWidthM\s*=\s*([0-9.eE+-]+)', geo)
if not inner_match or not width_match:
    fail("parameterized TX winding dimensions are missing")
x0 = float(inner_match.group(1))
width = float(width_match.group(1))
height = 0.010

if not (width > 0 and height > 0 and x0 >= 0):
    fail("TX winding cross-section dimensions are invalid")
area = width * height
mid_time = (start + end) / 2.0
j_peak = coefficient * (
    math.tanh((mid_time - start) / rise_width)
    - math.tanh((mid_time - end) / fall_width)
)
equivalent_total_current = j_peak * area

if 'Physical Surface("TX_Coil", 2)' not in geo:
    fail("TX_Coil physical group ID 2 is missing")
if 'Physical Surface("Aluminium_Target", 3)' not in geo:
    fail("Aluminium_Target physical group ID 3 is missing")
if "Current Density = Variable time" not in sif:
    fail("time-varying current density declaration is missing")

tx_body = re.search(
    r'Body\s+2\s+Name\s*=\s*"TX_Coil"(.*?)\nEnd',
    sif,
    flags=re.IGNORECASE | re.DOTALL,
)
if not tx_body or not re.search(r"Body\s+Force\s*=\s*1", tx_body.group(1), re.IGNORECASE):
    fail("TX_Coil body is not explicitly linked to Body Force 1")
if not re.search(
    r'Body\s+Force\s+1\s+Name\s*=\s*"TX_Pulse".*?Current\s+Density\s*=\s*Variable\s+time',
    sif,
    flags=re.IGNORECASE | re.DOTALL,
):
    fail("TX_Pulse body force does not define the time-dependent current source")
if not re.search(
    r'Material\s+3\s+Name\s*=\s*"Aluminium".*?Electric\s+Conductivity\s*=\s*3\.5e7',
    sif,
    flags=re.IGNORECASE | re.DOTALL,
):
    fail("Aluminium target conductivity is missing or changed")

# The present homogenized model encodes 20 A-turn total in the winding pack.
expected_ampere_turns = 20.0
if not math.isclose(equivalent_total_current, expected_ampere_turns, rel_tol=2e-3):
    fail(
        "excitation/geometry mismatch: "
        f"J_peak={j_peak:.9g} A/m^2, area={area:.9g} m^2, "
        f"integral={equivalent_total_current:.9g} A-turn; "
        f"expected {expected_ampere_turns:g} A-turn"
    )

print("PASS: PI excitation definition is dimensionally consistent")
print(f"Pulse window: {start*1e6:.3f}–{end*1e6:.3f} us")
print(f"TX cross-section: {width*1e3:.3f} x {height*1e3:.3f} mm")
print(f"Peak current density: {j_peak:.6g} A/m^2")
print(f"Equivalent integrated excitation: {equivalent_total_current:.6g} A-turn")
print("NOTE: static input check only; FEM stability and physical validation remain separate gates")
