#!/usr/bin/env python3
"""Check a nominal DD32 TX-coil RL pulse decay against its closed-form solution."""
import math
import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: verify_tx_rl_decay.py NGSPICE_LOG")

log = Path(sys.argv[1]).read_text(errors="replace")

def measured(name):
    match = re.search(
        rf"^\s*{name}\s*=\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
        log, re.I | re.M
    )
    if not match:
        raise SystemExit(f"FAIL: ngspice measurement {name} was not found")
    return float(match.group(1))

resistance = 1.52
inductance = 350e-6
voltage = 1.0
pulse_width = 200e-6
decay_elapsed = 300e-6
i_on_expected = voltage / resistance * (1.0 - math.exp(-resistance * pulse_width / inductance))
i_off_expected = i_on_expected * math.exp(-resistance * decay_elapsed / inductance)
i_on = measured("i_on")
i_off = measured("i_off")
if i_on <= 0 or i_off <= 0 or i_off >= i_on:
    raise SystemExit("FAIL: measured RL current decay is not positive and monotonic")

tau_measured = -decay_elapsed / math.log(i_off / i_on)
tau_expected = inductance / resistance
error_on = abs(i_on - i_on_expected)
error_off = abs(i_off - i_off_expected)
error_tau = abs(tau_measured - tau_expected)

print(f"Measured current at pulse end  = {i_on:.6f} A (expected {i_on_expected:.6f} A)")
print(f"Measured current 300 us later = {i_off:.6f} A (expected {i_off_expected:.6f} A)")
print(f"Measured decay tau             = {tau_measured * 1e6:.3f} us (expected {tau_expected * 1e6:.3f} us)")
print(f"Absolute errors                = {error_on:.6f} A, {error_off:.6f} A, {error_tau * 1e6:.3f} us")

if error_on > 0.002 or error_off > 0.002 or error_tau > 5e-6:
    raise SystemExit("FAIL: ngspice RL decay differs from the analytical reference")
print("PASS: nominal TX coil RL pulse decay agrees with the analytical solution")
