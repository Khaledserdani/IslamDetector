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



def valid_window_mask(
    delay_windows_s: list[float],
    recovery_budget_s: float,
) -> int:
    """Return VALID_MASK bits for windows at/after a conservative recovery time.

    Bit i corresponds to delay_windows_s[i]. The caller must still apply
    hardware-derived quality flags; this timing-only mask is not a signal
    quality classifier.
    """
    budget = _positive_finite("recovery_budget_s", recovery_budget_s, allow_zero=True)
    if not delay_windows_s:
        raise ValueError("delay_windows_s must not be empty")
    previous = -1.0
    mask = 0
    for index, raw_delay in enumerate(delay_windows_s):
        delay = _positive_finite(f"delay_windows_s[{index}]", raw_delay)
        if delay <= previous:
            raise ValueError("delay_windows_s must be strictly increasing")
        if delay >= budget:
            mask |= 1 << index
        previous = delay
    return mask


def square_spiral_estimate(
    outer_side_m: float,
    turns: int,
    wire_diameter_m: float,
    gap_m: float,
    copper_diameter_m: float,
) -> dict[str, float]:
    """First-order geometry estimate for a flat square air-core spiral.

    Uses modified-Wheeler and current-sheet approximations attributed to
    Mohan et al. (1999), plus geometric wire-length and 20 C copper DCR
    estimates. Not validated here for a 35 cm hand-wound PI search head;
    treat outputs as a screening range, not measured values.
    outer_side_m is the outside dimension; outer turn centerline is
    approximated as outer_side_m - wire_diameter_m.
    """
    side = _positive_finite("outer_side_m", outer_side_m)
    wire = _positive_finite("wire_diameter_m", wire_diameter_m)
    gap = _positive_finite("gap_m", gap_m, allow_zero=True)
    copper = _positive_finite("copper_diameter_m", copper_diameter_m)
    if not isinstance(turns, int) or isinstance(turns, bool) or turns < 2:
        raise ValueError("turns must be an integer of at least two for a spiral")
    if copper > wire:
        raise ValueError("copper_diameter_m cannot exceed wire_diameter_m")

    pitch = wire + gap
    outer_centerline = side - wire
    inner_centerline = outer_centerline - 2.0 * (turns - 1) * pitch
    if inner_centerline <= 0:
        raise ValueError("winding geometry collapses: inner opening is not positive")

    d_avg = 0.5 * (outer_centerline + inner_centerline)
    rho = (outer_centerline - inner_centerline) / (outer_centerline + inner_centerline)
    mu0 = 4.0 * math.pi * 1e-7

    # Square-layout coefficients from Mohan et al., IEEE JSSC 34(10), 1999.
    inductance_wheeler_h = 2.34 * mu0 * turns * turns * d_avg / (1.0 + 2.75 * rho)
    inductance_current_sheet_h = (
        mu0 * turns * turns * d_avg * 1.27 / 2.0
        * (math.log(2.07 / rho) + 0.18 * rho + 0.13 * rho * rho)
    )

    wire_length_m = 4.0 * sum(
        outer_centerline - 2.0 * index * pitch
        for index in range(turns)
    )
    copper_area_m2 = math.pi * (copper / 2.0) ** 2
    copper_resistivity_20c_ohm_m = 1.724e-8
    dcr_20c_ohm = copper_resistivity_20c_ohm_m * wire_length_m / copper_area_m2

    return {
        "outer_centerline_side_m": outer_centerline,
        "inner_centerline_side_m": inner_centerline,
        "average_side_m": d_avg,
        "fill_ratio": rho,
        "wire_length_m": wire_length_m,
        "dcr_20c_ohm": dcr_20c_ohm,
        "inductance_wheeler_h": inductance_wheeler_h,
        "inductance_current_sheet_h": inductance_current_sheet_h,
    }


def square_spiral_axis_field(
    outer_side_m: float,
    turns: int,
    wire_diameter_m: float,
    gap_m: float,
    current_a: float,
    depth_m: float = 0.0,
) -> float:
    """Ideal axial B-field from concentric square turns carrying equal current.

    Returns tesla at a point on the normal axis, depth_m from the coil plane.
    This is a free-space thin-wire field estimate; it excludes target coupling,
    soil, ferrite/shielding, nearby conductors and current redistribution.
    """
    current = _positive_finite("current_a", current_a, allow_zero=True)
    depth = _positive_finite("depth_m", depth_m, allow_zero=True)
    # Reuse geometry validation and its centerline convention.
    geometry = square_spiral_estimate(
        outer_side_m, turns, wire_diameter_m, gap_m, wire_diameter_m
    )
    outer_centerline = geometry["outer_centerline_side_m"]
    pitch = float(wire_diameter_m) + float(gap_m)
    mu0 = 4.0 * math.pi * 1e-7
    field_t = 0.0
    for index in range(turns):
        side = outer_centerline - 2.0 * index * pitch
        radius_squared = (side / 2.0) ** 2 + depth * depth
        field_t += (
            mu0 * current * side * side
            / (2.0 * math.pi * radius_squared * math.sqrt(side * side / 2.0 + depth * depth))
        )
    return field_t


def low_side_clamp_stress(
    supply_v: float,
    coil_inductance_h: float,
    coil_resistance_ohm: float,
    initial_current_a: float,
    opposing_clamp_v: float,
    pulse_rate_hz: float,
    final_current_a: float = 0.0,
) -> dict[str, float]:
    """Estimate energy and voltage stress for a low-side NMOS coil switch.

    Assumes a series-RL coil fed from supply_v, with a constant opposing
    clamp voltage across the coil during turn-off. The ideal switch voltage
    is supply_v + opposing_clamp_v; real VDS also includes parasitic overshoot.
    The clamp absorbs the portion of magnetic energy not dissipated in the
    coil resistance. This is not a TVS selection or MOSFET SOA calculator.
    """
    supply = _positive_finite("supply_v", supply_v)
    inductance = _positive_finite("coil_inductance_h", coil_inductance_h)
    resistance = _positive_finite("coil_resistance_ohm", coil_resistance_ohm, allow_zero=True)
    current = _positive_finite("initial_current_a", initial_current_a)
    clamp = _positive_finite("opposing_clamp_v", opposing_clamp_v)
    rate = _positive_finite("pulse_rate_hz", pulse_rate_hz)
    final = _positive_finite("final_current_a", final_current_a, allow_zero=True)
    if final >= current:
        raise ValueError("final_current_a must be lower than initial_current_a")

    initial_energy = stored_energy(inductance, current)
    final_energy = stored_energy(inductance, final)
    released_energy = initial_energy - final_energy
    if resistance == 0.0:
        clamp_energy = released_energy
    else:
        delta_i = current - final
        x = resistance * delta_i / (clamp + resistance * final)
        integral_i_dt = inductance * (
            delta_i / resistance
            - clamp / (resistance * resistance) * math.log1p(x)
        )
        clamp_energy = clamp * integral_i_dt
        # Guard only tiny floating-point round-off; a real negative value is invalid.
        if clamp_energy < -1e-12 or clamp_energy > released_energy + 1e-12:
            raise ArithmeticError("energy balance outside physical bounds")
        clamp_energy = min(max(clamp_energy, 0.0), released_energy)

    coil_resistive_loss = released_energy - clamp_energy
    decay_s = clamp_decay_time(
        inductance, resistance, clamp, current, final
    )
    return {
        "initial_magnetic_energy_j": initial_energy,
        "remaining_magnetic_energy_j": final_energy,
        "released_magnetic_energy_j": released_energy,
        "clamp_energy_per_pulse_j": clamp_energy,
        "coil_resistive_loss_per_pulse_j": coil_resistive_loss,
        "clamp_average_power_w": clamp_energy * rate,
        "coil_average_decay_loss_w": coil_resistive_loss * rate,
        "ideal_mosfet_vds_v": supply + clamp,
        "peak_clamp_current_a": current,
        "current_decay_s": decay_s,
    }
