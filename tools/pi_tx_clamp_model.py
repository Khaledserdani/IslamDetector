#!/usr/bin/env python3
"""First-order PI TX flyback-clamp model for ISLAM NEXTGEN.

This is a transparent piecewise RL model, NOT SPICE and NOT a hardware measurement.
The TVS is approximated by a linear breakdown/dynamic-resistance segment.
The clamp is across the TX coil: a bidirectional TVS string in parallel with
a series resistor + fast diode branch oriented to conduct only during flyback.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Result:
    inductance_uH: float
    current_A: float
    clamp_resistance_ohm: float
    decay_us: float
    initial_energy_mJ: float
    resistor_energy_mJ: float
    tvs_energy_mJ: float
    diode_energy_mJ: float
    coil_copper_energy_mJ: float
    energy_error_percent: float
    peak_coil_voltage_V: float
    peak_mosfet_vds_V: float
    average_resistor_W_at_1kHz: float
    average_tvs_W_at_1kHz: float


def simulate(
    inductance_uH: float = 175.8,
    current_A: float = 5.0,
    coil_resistance_ohm: float = 1.04,
    clamp_resistance_ohm: float = 47.0,
    diode_forward_V: float = 1.5,
    tvs_count: int = 3,
    tvs_vbr_single_V: float = 41.0,
    tvs_vclamp_single_V: float = 53.9,
    tvs_ipp_A: float = 28.2,
    battery_V: float = 12.0,
    step_us: float = 0.02,
) -> Result:
    """Integrate the turn-off current and energy split with midpoint stepping."""
    L = inductance_uH * 1e-6
    dt = step_us * 1e-6
    vbr = tvs_count * tvs_vbr_single_V
    vclamp = tvs_count * tvs_vclamp_single_V
    rd = (vclamp - vbr) / tvs_ipp_A

    def branch_values(current: float) -> tuple[float, float, float]:
        if current <= 0:
            return 0.0, 0.0, 0.0
        threshold = (vbr - diode_forward_V) / clamp_resistance_ohm
        if current <= threshold:
            voltage = diode_forward_V + current * clamp_resistance_ohm
            resistor_current = current
            tvs_current = 0.0
        else:
            voltage = (
                current
                + diode_forward_V / clamp_resistance_ohm
                + vbr / rd
            ) / (1.0 / clamp_resistance_ohm + 1.0 / rd)
            resistor_current = (voltage - diode_forward_V) / clamp_resistance_ohm
            tvs_current = (voltage - vbr) / rd
        return voltage, resistor_current, tvs_current

    current = current_A
    time_s = 0.0
    e_resistor = 0.0
    e_tvs = 0.0
    e_diode = 0.0
    e_coil = 0.0
    peak_coil_voltage = 0.0

    while current > 1e-7 and time_s < 0.01:
        voltage, _, _ = branch_values(current)
        di_dt = -(voltage + current * coil_resistance_ohm) / L
        midpoint_current = max(0.0, current + 0.5 * di_dt * dt)
        midpoint_voltage, resistor_current, tvs_current = branch_values(midpoint_current)

        e_resistor += resistor_current**2 * clamp_resistance_ohm * dt
        e_tvs += midpoint_voltage * tvs_current * dt
        e_diode += diode_forward_V * resistor_current * dt
        e_coil += midpoint_current**2 * coil_resistance_ohm * dt
        peak_coil_voltage = max(peak_coil_voltage, voltage)

        current = max(0.0, current + di_dt * dt)
        time_s += dt

    initial_energy = 0.5 * L * current_A**2
    accounted = e_resistor + e_tvs + e_diode + e_coil
    error = 100.0 * (accounted - initial_energy) / initial_energy

    return Result(
        inductance_uH=inductance_uH,
        current_A=current_A,
        clamp_resistance_ohm=clamp_resistance_ohm,
        decay_us=time_s * 1e6,
        initial_energy_mJ=initial_energy * 1e3,
        resistor_energy_mJ=e_resistor * 1e3,
        tvs_energy_mJ=e_tvs * 1e3,
        diode_energy_mJ=e_diode * 1e3,
        coil_copper_energy_mJ=e_coil * 1e3,
        energy_error_percent=error,
        peak_coil_voltage_V=peak_coil_voltage,
        peak_mosfet_vds_V=battery_V + peak_coil_voltage,
        average_resistor_W_at_1kHz=e_resistor * 1000.0,
        average_tvs_W_at_1kHz=e_tvs * 1000.0,
    )


def main() -> None:
    print(
        "L_uH,I_A,decay_us,E0_mJ,R_mJ,TVS_mJ,D_mJ,coil_mJ,"
        "energy_error_pct,Vcoil_peak_V,Vds_peak_V,R_avg_W,TVS_avg_W"
    )
    for inductance in (175.8, 240.0, 300.0, 400.0):
        for current in (5.0, 6.0):
            r = simulate(inductance_uH=inductance, current_A=current)
            print(
                f"{r.inductance_uH:.0f},{r.current_A:.1f},{r.decay_us:.2f},"
                f"{r.initial_energy_mJ:.3f},{r.resistor_energy_mJ:.3f},"
                f"{r.tvs_energy_mJ:.3f},{r.diode_energy_mJ:.3f},"
                f"{r.coil_copper_energy_mJ:.3f},{r.energy_error_percent:.3f},"
                f"{r.peak_coil_voltage_V:.2f},{r.peak_mosfet_vds_V:.2f},"
                f"{r.average_resistor_W_at_1kHz:.3f},"
                f"{r.average_tvs_W_at_1kHz:.3f}"
            )


if __name__ == "__main__":
    main()
