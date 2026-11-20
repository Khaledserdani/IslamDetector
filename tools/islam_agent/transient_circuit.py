"""Bounded series-RLC AC and transient laboratory.

This is an ideal lumped single-loop model, not a general-purpose SPICE engine.
Transient response uses fixed-step RK4; AC uses exact sinusoidal phasors.
"""
from __future__ import annotations

import math

MAX_DURATION_S = 20.0
MAX_STEP_S = 0.001
MAX_SAMPLES = 100_000
MAX_COMPONENT = 1e6
MAX_VOLTAGE = 10_000.0


class RLCInputError(ValueError):
    pass


def validate_rlc(spec):
    if not isinstance(spec, dict):
        raise RLCInputError("RLC input must be an object")
    mode = spec.get("mode")
    common = {"mode", "resistance_ohm", "inductance_h", "capacitance_f", "source_voltage_v"}
    required = common | ({"duration_s", "time_step_s", "initial_current_a", "initial_capacitor_voltage_v"} if mode == "transient" else {"frequency_hz"} if mode == "ac" else set())
    if not required or set(spec) != required:
        raise RLCInputError("RLC fields do not match the selected mode")
    def number(key, low, high, *, inclusive=True):
        value = spec[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise RLCInputError(key + " must be a finite number")
        if value < low or value > high or (not inclusive and value == low):
            raise RLCInputError(key + " is outside safe laboratory bounds")
        return float(value)
    r = number("resistance_ohm", 0.0, MAX_COMPONENT)
    l = number("inductance_h", 0.0, MAX_COMPONENT, inclusive=False)
    c = number("capacitance_f", 0.0, MAX_COMPONENT, inclusive=False)
    v = number("source_voltage_v", -MAX_VOLTAGE, MAX_VOLTAGE)
    if mode == "transient":
        duration = number("duration_s", 1e-7, MAX_DURATION_S, inclusive=False)
        dt = number("time_step_s", 1e-9, MAX_STEP_S, inclusive=False)
        if math.ceil(duration / dt) + 1 > MAX_SAMPLES:
            raise RLCInputError("transient sample count exceeds the 100000 point limit")
        i0 = number("initial_current_a", -1e4, 1e4)
        vc0 = number("initial_capacitor_voltage_v", -MAX_VOLTAGE, MAX_VOLTAGE)
        return mode, r, l, c, v, duration, dt, i0, vc0
    frequency = number("frequency_hz", 1e-6, 1e7, inclusive=False)
    return mode, r, l, c, v, frequency


def simulate_series_rlc(spec):
    values = validate_rlc(spec)
    mode = values[0]
    if mode == "ac":
        _, r, l, c, voltage, frequency = values
        omega = 2.0 * math.pi * frequency
        x_l = omega * l
        x_c = 1.0 / (omega * c)
        reactance = x_l - x_c
        impedance = math.hypot(r, reactance)
        if impedance < 1e-15:
            raise RLCInputError("ideal zero-impedance resonance is unbounded; add realistic series resistance")
        current = abs(voltage) / impedance
        phase = -math.atan2(reactance, r)
        pf = (r / impedance) if impedance else 0.0
        return {
            "laboratory": "series_rlc_ac_phasor",
            "model": "ideal single-loop series RLC at sinusoidal steady state",
            "frequency_hz": frequency, "omega_rad_s": omega,
            "inductive_reactance_ohm": x_l, "capacitive_reactance_ohm": x_c,
            "impedance_magnitude_ohm": impedance,
            "current_rms_a": current, "current_phase_deg": math.degrees(phase),
            "power_factor": pf,
            "real_power_w": current * current * r,
            "verified_numerically": math.isfinite(current) and math.isfinite(pf),
            "limitations": ["لا يحاكي التوافقيات أو العناصر غير الخطية أو الاقتران أو الطفيليات أو الدوائر متعددة الحلقات."],
        }

    _, r, l, c, source, duration, dt, current, vc = values
    def derivative(i, capacitor_v):
        return ((source - r * i - capacitor_v) / l, i / c)
    times, currents, capacitor_voltages, inductor_voltages = [], [], [], []
    steps = int(math.ceil(duration / dt))
    for index in range(steps + 1):
        t = min(index * dt, duration)
        di, dvc = derivative(current, vc)
        times.append(t)
        currents.append(current)
        capacitor_voltages.append(vc)
        inductor_voltages.append(source - r * current - vc)
        if index == steps:
            break
        h = min(dt, duration - t)
        k1i, k1v = derivative(current, vc)
        k2i, k2v = derivative(current + 0.5*h*k1i, vc + 0.5*h*k1v)
        k3i, k3v = derivative(current + 0.5*h*k2i, vc + 0.5*h*k2v)
        k4i, k4v = derivative(current + h*k3i, vc + h*k3v)
        current += h * (k1i + 2*k2i + 2*k3i + k4i) / 6.0
        vc += h * (k1v + 2*k2v + 2*k3v + k4v) / 6.0
        if not math.isfinite(current) or not math.isfinite(vc) or abs(current) > 1e9 or abs(vc) > 1e9:
            raise RLCInputError("transient solution became numerically unstable; reduce step size or review parameters")
    energy = [0.5*l*i*i + 0.5*c*v*v for i, v in zip(currents, capacitor_voltages)]
    return {
        "laboratory": "series_rlc_transient_rk4",
        "model": "ideal single-loop series RLC with constant DC step source",
        "time_s": times, "current_a": currents,
        "capacitor_voltage_v": capacitor_voltages,
        "inductor_voltage_v": inductor_voltages,
        "stored_energy_j": energy,
        "sample_count": len(times), "time_step_s": dt,
        "verified_numerically": all(math.isfinite(x) for seq in (currents, capacitor_voltages, inductor_voltages, energy) for x in seq),
        "limitations": ["لا يحاكي التبديل العام أو مصادر موجية مخصصة أو أشباه الموصلات أو الحرارة أو الطفيليات أو دوائر متعددة الحلقات."],
    }
