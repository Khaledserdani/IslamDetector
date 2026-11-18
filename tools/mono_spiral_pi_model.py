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



def charge_injection_step(
    feedthrough_capacitance_f: float,
    switching_step_v: float,
    total_node_capacitance_f: float,
) -> float:
    """First-order receiver-node voltage step from capacitive feedthrough.

    This is a charge-sharing estimate, not a switch datasheet model. The
    effective capacitances and edge waveform must be obtained from the
    selected switch, PCB layout and measurement.
    """
    c_feed = _positive_finite(
        "feedthrough_capacitance_f", feedthrough_capacitance_f, allow_zero=True
    )
    dv = _positive_finite("switching_step_v", switching_step_v, allow_zero=True)
    c_total = _positive_finite("total_node_capacitance_f", total_node_capacitance_f)
    return c_feed * dv / c_total


def rc_recovery_time(
    resistance_ohm: float,
    capacitance_f: float,
    initial_error_v: float,
    allowed_error_v: float,
) -> float:
    """Time for a first-order RC residual to decay within an error band."""
    r = _positive_finite("resistance_ohm", resistance_ohm)
    c = _positive_finite("capacitance_f", capacitance_f)
    initial = _positive_finite("initial_error_v", initial_error_v, allow_zero=True)
    allowed = _positive_finite("allowed_error_v", allowed_error_v)
    if initial <= allowed:
        return 0.0
    return r * c * math.log(initial / allowed)


def serial_recovery_budget(
    coil_decay_s: float,
    switch_settle_s: float,
    amplifier_recovery_s: float,
    rc_recovery_s: float,
    adc_acquisition_s: float,
    guard_s: float = 0.0,
) -> float:
    """Conservative serial budget before the first candidate ADC sample.

    The sum intentionally assumes the stages recover sequentially. If
    measured waveforms prove overlap, replace this conservative sum with
    the measured critical-path timing. This is not a substitute for
    verifying linear operation and ADC settling on the actual circuit.
    """
    stages = {
        "coil_decay_s": coil_decay_s,
        "switch_settle_s": switch_settle_s,
        "amplifier_recovery_s": amplifier_recovery_s,
        "rc_recovery_s": rc_recovery_s,
        "adc_acquisition_s": adc_acquisition_s,
        "guard_s": guard_s,
    }
    return sum(
        _positive_finite(name, value, allow_zero=True)
        for name, value in stages.items()
    )
