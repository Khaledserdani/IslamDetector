#!/usr/bin/env python3
"""Compare ngspice's RLC step response with the closed-form underdamped solution."""
import math
import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: verify_series_rlc.py NGSPICE_LOG")

log = Path(sys.argv[1]).read_text(errors="replace")
match = re.search(r"v_tau\\s*=\\s*([-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][-+]?\\d+)?)", log, re.I)
if not match:
    raise SystemExit("FAIL: ngspice measurement v_tau was not found in its log")

measured = float(match.group(1))
resistance = 100.0
inductance = 10e-3
capacitance = 1e-6
elapsed = 0.2e-3
alpha = resistance / (2.0 * inductance)
omega_0 = 1.0 / math.sqrt(inductance * capacitance)
if alpha >= omega_0:
    raise SystemExit("FAIL: reference circuit is not underdamped")
omega_d = math.sqrt(omega_0**2 - alpha**2)
expected = 1.0 - math.exp(-alpha * elapsed) * (
    math.cos(omega_d * elapsed) + (alpha / omega_d) * math.sin(omega_d * elapsed)
)
error = abs(measured - expected)
tolerance = 0.015
print(f"ngspice measured Vc(0.2 ms) = {measured:.6f} V")
print(f"Analytical expected value   = {expected:.6f} V")
print(f"Absolute error              = {error:.6f} V (limit {tolerance:.3f} V)")
if error > tolerance:
    raise SystemExit("FAIL: RLC transient differs from analytical reference")
print("PASS: ngspice RLC reference agrees with the analytical solution")
