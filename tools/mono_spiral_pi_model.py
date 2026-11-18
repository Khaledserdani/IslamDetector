"""Parameterized first-order PI coil model.

All inputs use SI units. This is an ideal series-RL / constant-opposing-clamp
model for design exploration only; it is not a hardware measurement or a
switch/TVS/snubber rating calculator.
"""
from __future__ import annotations

import math


def _positive_finite(name: str, value: float, *, allow_zero: bool = False) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0 or (value == 0 and not allow_zero):
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {qualifier}")
    return value


def pulse_current(
    supply_v: float,
    coil_resistance_ohm: float,
    coil_inductance_h: float,
    pulse_width_s: float,
) -> float:
    """Ideal series-RL current at the end of a constant-voltage TX pulse."""
    v = _positive_finite("supply_v", supply_v)
    r = _positive_finite("coil_resistance_ohm", coil_resistance_ohm, allow_zero=True)
    l = _positive_finite("coil_inductance_h", coil_inductance_h)
    t = _positive_finite("pulse_width_s", pulse_width_s, allow_zero=True)
    if r == 0:
        return v * t / l
    return (v / r) * (-math.expm1(-t * r / l))


def stored_energy(coil_inductance_h: float, current_a: float) -> float:
    """Magnetic energy in an ideal inductor: 0.5 * L * I**2."""
    l = _positive_finite("coil_inductance_h", coil_inductance_h)
    i = _positive_finite("current_a", current_a, allow_zero=True)
    return 0.5 * l * i * i


def clamp_decay_time(
    coil_inductance_h: float,
    coil_resistance_ohm: float,
    opposing_clamp_v: float,
    initial_current_a: float,
    final_current_a: float = 0.0,
) -> float:
    """Idealized time for current to fall from I0 to If under a constant
    opposing clamp voltage and series coil resistance.

    The clamp voltage is defined as opposing the existing coil current.
    Parasitics, nonlinear clamp behavior, switch dynamics and layout are
    intentionally excluded.
    """
    l = _positive_finite("coil_inductance_h", coil_inductance_h)
    r = _positive_finite("coil_resistance_ohm", coil_resistance_ohm, allow_zero=True)
    vc = _positive_finite("opposing_clamp_v", opposing_clamp_v)
    i0 = _positive_finite("initial_current_a", initial_current_a)
    i1 = _positive_finite("final_current_a", final_current_a, allow_zero=True)
    if i1 >= i0:
        raise ValueError("final_current_a must be lower than initial_current_a")
    if r == 0:
        return l * (i0 - i1) / vc
    return (l / r) * math.log((i0 + vc / r) / (i1 + vc / r))
