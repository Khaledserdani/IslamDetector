"""Axisymmetric angular kernel for finite-section conducting-disk models.

This module integrates the azimuthal angles analytically for two axisymmetric
azimuthal-current elements. It does NOT yet integrate over their finite
(r, z) cross-sections; that remaining weakly singular 2-D-by-2-D integral
requires singularity-aware quadrature.
"""
from __future__ import annotations

import math

MU0 = 4.0 * math.pi * 1.0e-7


def _complete_elliptic_ke(parameter: float) -> tuple[float, float]:
    """Complete elliptic integrals K(m), E(m), with parameter m=k**2."""
    if not math.isfinite(parameter) or not 0.0 <= parameter < 1.0:
        raise ValueError("elliptic parameter must be finite and in [0, 1)")
    a = 1.0
    b = math.sqrt(1.0 - parameter)
    correction = 0.5 * parameter
    weight = 1.0
    for _ in range(80):
        c = 0.5 * (a - b)
        if abs(c) <= 2.0e-16 * a:
            break
        correction += weight * c * c
        a_next = 0.5 * (a + b)
        b = math.sqrt(a * b)
        a = a_next
        weight *= 2.0
    else:
        raise ArithmeticError("elliptic AGM iteration did not converge")
    complete_k = math.pi / (2.0 * a)
    complete_e = complete_k * (1.0 - correction)
    return complete_k, complete_e


def azimuthal_cosine_kernel_per_m(
    radius_a_m: float, z_a_m: float,
    radius_b_m: float, z_b_m: float,
) -> float:
    """Return integral_0^(2pi) cos(theta)/distance dtheta [1/m].

    The two source points have cylindrical radii radius_a_m and radius_b_m.
    The azimuthal current directions have dot product cos(theta).

    This is the single relative-angle integral. The double integral over both
    absolute azimuths is 2*pi times this value. Coincident meridional points
    are singular and rejected; their singularity is integrable only after
    integration over finite cross-sectional cells.
    """
    values = (radius_a_m, z_a_m, radius_b_m, z_b_m)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("coordinates must be finite")
    if radius_a_m < 0.0 or radius_b_m < 0.0:
        raise ValueError("cylindrical radii must be non-negative")
    if radius_a_m == 0.0 or radius_b_m == 0.0:
        return 0.0

    axial = z_a_m - z_b_m
    a = radius_a_m * radius_a_m + radius_b_m * radius_b_m + axial * axial
    b = 2.0 * radius_a_m * radius_b_m
    if a <= b:
        raise ValueError("coincident meridional points produce a singular kernel")

    q = b / a
    root_a = math.sqrt(a)
    # The elliptic expression subtracts nearly equal terms for small q.
    if q < 1.0e-3:
        # Integral = pi/sqrt(a) * (q/2 + 15q^3/64
        # + 315q^5/2048 + 15015q^7/131072 + ...).
        q2 = q * q
        series = q * (
            0.5 + q2 * (15.0 / 64.0 + q2 * (
                315.0 / 2048.0 + q2 * (15015.0 / 131072.0)
            ))
        )
        return math.pi * series / root_a

    parameter = 2.0 * b / (a + b)
    complete_k, complete_e = _complete_elliptic_ke(parameter)
    root_sum = math.sqrt(a + b)
    return (4.0 / b) * (
        a * complete_k / root_sum - root_sum * complete_e
    )


def azimuthally_integrated_neumann_kernel_per_m(
    radius_a_m: float, z_a_m: float,
    radius_b_m: float, z_b_m: float,
) -> float:
    """Return the double-azimuth Neumann kernel [1/m]."""
    return 2.0 * math.pi * azimuthal_cosine_kernel_per_m(
        radius_a_m, z_a_m, radius_b_m, z_b_m
    )


def finite_cell_inductance_integrand_h_per_m4(
    radius_a_m: float, z_a_m: float,
    radius_b_m: float, z_b_m: float,
    area_a_m2: float, area_b_m2: float,
) -> float:
    """Point-pair density for unit-current uniform meridional cell bases [H/m^4].

    This is the integrand multiplying dr dz dr' dz' in the finite-cell
    inductance double integral. It is not a cell inductance. Do not evaluate
    it at centroids as a replacement for finite-cell integration.
    """
    if not math.isfinite(area_a_m2) or not math.isfinite(area_b_m2):
        raise ValueError("cell areas must be finite")
    if area_a_m2 <= 0.0 or area_b_m2 <= 0.0:
        raise ValueError("cell areas must be positive")
    angular = azimuthally_integrated_neumann_kernel_per_m(
        radius_a_m, z_a_m, radius_b_m, z_b_m
    )
    return (
        MU0 / (4.0 * math.pi)
        * radius_a_m * radius_b_m
        / (area_a_m2 * area_b_m2)
        * angular
    )
