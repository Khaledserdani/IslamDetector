"""Frequency-scale helpers for copper conductors in the Mono Spiral PI study.

These functions calculate classical sinusoidal skin-depth reference scales.
They do not model a complete PI pulse, proximity effect, or coil impedance.
"""
from __future__ import annotations

import math

MU0_H_PER_M = 4.0 * math.pi * 1e-7
COPPER_RESISTIVITY_20C_OHM_M = 1.724e-8


def _require_positive_finite(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive")


def skin_depth_m(
    frequency_hz: float,
    resistivity_ohm_m: float = COPPER_RESISTIVITY_20C_OHM_M,
    relative_permeability: float = 1.0,
) -> float:
    """Return classical sinusoidal skin depth in metres.

    delta = sqrt(rho / (pi * mu0 * mur * f)).
    This is a frequency-domain reference, not a transient PI solution.
    """
    _require_positive_finite("frequency_hz", frequency_hz)
    _require_positive_finite("resistivity_ohm_m", resistivity_ohm_m)
    _require_positive_finite("relative_permeability", relative_permeability)
    return math.sqrt(
        resistivity_ohm_m
        / (math.pi * MU0_H_PER_M * relative_permeability * frequency_hz)
    )


def frequency_at_skin_depth_m(
    conductor_radius_m: float,
    resistivity_ohm_m: float = COPPER_RESISTIVITY_20C_OHM_M,
    relative_permeability: float = 1.0,
) -> float:
    """Return f where classical skin depth equals the supplied radius.

    This is a gradual crossover scale, not a sharp onset threshold.
    """
    _require_positive_finite("conductor_radius_m", conductor_radius_m)
    _require_positive_finite("resistivity_ohm_m", resistivity_ohm_m)
    _require_positive_finite("relative_permeability", relative_permeability)
    return resistivity_ohm_m / (
        math.pi * MU0_H_PER_M * relative_permeability * conductor_radius_m**2
    )


def first_order_edge_knee_hz(rise_time_10_90_s: float) -> float:
    """Estimate a first-order 10-90% edge bandwidth scale as 0.35 / tr.

    This is only a rough edge-knee estimate. It is not a spectral cutoff and
    must not replace FFT analysis of the measured coil-current waveform.
    """
    _require_positive_finite("rise_time_10_90_s", rise_time_10_90_s)
    return 0.35 / rise_time_10_90_s
