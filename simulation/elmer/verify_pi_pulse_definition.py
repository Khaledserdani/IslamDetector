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

coil_match = re.search(
    r'Rectangle\s*\(\s*3\s*\)\s*=\s*\{([^}]+)\}',
    geo,
)
if not coil_match:
    fail("TX winding rectangle (Rectangle 3) not found in Gmsh geometry")
try:
    x0, z0, _zcoord, width, height = [
        float(part.strip()) for part in coil_match.group(1).split(",")
    ]
except (ValueError, TypeError):
    fail("could not parse TX winding rectangle coordinates")

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
