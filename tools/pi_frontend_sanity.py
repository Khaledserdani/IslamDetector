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


def bucking_gyrator(r_var_ohm: float, r_ohm: float, c_f: float) -> tuple[float, float]:
    """Return equivalent inductance and exponential time constant."""
    return r_var_ohm * r_ohm * c_f, r_var_ohm * c_f


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
