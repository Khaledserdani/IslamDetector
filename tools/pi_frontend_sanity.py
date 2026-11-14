#!/usr/bin/env python3
"""First-order sanity calculations for ISLAM NEXTGEN PI timing.

No SPICE, parasitics, target model, or hardware measurement is included.
This script is intended to prevent inconsistent pulse/coil assumptions.
"""

from __future__ import annotations

from math import exp, log


def coil_current(v_supply: float, r_coil: float, l_h: float, pulse_s: float) -> float:
    """Ideal series-RL current at the end of a voltage pulse."""
    tau = l_h / r_coil
    return (v_supply / r_coil) * (1.0 - exp(-pulse_s / tau))


def time_to_current(v_supply: float, r_coil: float, l_h: float, target_a: float) -> float:
    """Ideal time required to reach target current; infinity if unreachable."""
    i_inf = v_supply / r_coil
    if target_a >= i_inf:
        return float("inf")
    return -(l_h / r_coil) * log(1.0 - target_a / i_inf)



def coil_copper_ramp_energy(
    v_supply: float, r_coil: float, l_h: float, target_a: float
) -> tuple[float, float]:
    """Return time and I²R copper energy during an ideal RL current ramp.

    Excludes flyback/turn-off decay, switching, and parasitic losses.
    """
    t = time_to_current(v_supply, r_coil, l_h, target_a)
    if not (t > 0.0 and t < float("inf")):
        raise ValueError("target current must be reachable and positive")
    tau = l_h / r_coil
    i_inf = v_supply / r_coil
    decay = exp(-t / tau)
    integral_i2 = i_inf**2 * (
        t - 2.0 * tau * (1.0 - decay)
        + 0.5 * tau * (1.0 - decay**2)
    )
    return t, r_coil * integral_i2


def bucking_gyrator(r_var_ohm: float, r_ohm: float, c_f: float) -> tuple[float, float]:
    """Return equivalent inductance and exponential time constant."""
    return r_var_ohm * r_ohm * c_f, r_var_ohm * c_f



def bucking_decay(
    vdc_b: float,
    r_ohm: float,
    switch_ron_ohm: float,
    r_var_ohm: float,
    c_f: float,
) -> tuple[float, float, float, float]:
    """Return Lvar, initial current, actual decay tau, and stored energy.

    The switch RON is included in the discharge resistance. This is still a
    first-order RL approximation, not a nonlinear gyrator/SPICE model.
    """
    l_var = r_var_ohm * r_ohm * c_f
    r_total = r_ohm + switch_ron_ohm
    i_initial = vdc_b / r_total
    tau_actual = l_var / r_total
    energy_j = 0.5 * l_var * i_initial**2
    return l_var, i_initial, tau_actual, energy_j


def main() -> None:
    v = 12.0
    r = 1.5
    pulse_s = 300e-6
    target_i = 5.0
    print("L_uH,I_end_at_300us_A,t_to_5A_us")
    for l_uH in (180.0, 240.0, 300.0, 400.0):
        l_h = l_uH * 1e-6
        i_end = coil_current(v, r, l_h, pulse_s)
        t5 = time_to_current(v, r, l_h, target_i)
        print(f"{l_uH:.0f},{i_end:.3f},{t5 * 1e6:.1f}")

    print("\nRvar_kOhm,Lvar_mH,tau_us")
    for rvar_k in (200.0, 250.0, 300.0):
        lvar, tau = bucking_gyrator(rvar_k * 1e3, 100.0, 100e-12)
        print(f"{rvar_k:.0f},{lvar * 1e3:.3f},{tau * 1e6:.1f}")


if __name__ == "__main__":
    main()
