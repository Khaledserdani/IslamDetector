"""Finite-length self-inductance of a straight rectangular-section conductor.

For a uniform axial current density, this evaluates the Neumann double
integral averaged over two independent points in the rectangular cross-section.
It is one segment's self term, not a closed-loop inductance by itself.
"""
from __future__ import annotations

import math

MU0 = 4.0 * math.pi * 1e-7


def _gauss_legendre(order: int) -> tuple[list[float], list[float]]:
    if order < 2:
        raise ValueError("quadrature order must be at least 2")
    nodes = [0.0] * order
    weights = [0.0] * order
    for i in range((order + 1) // 2):
        z = math.cos(math.pi * (i + 0.75) / (order + 0.5))
        for _ in range(100):
            p0, p1 = 1.0, z
            for degree in range(2, order + 1):
                p0, p1 = p1, ((2 * degree - 1) * z * p1 - (degree - 1) * p0) / degree
            derivative = order * (z * p1 - p0) / (z * z - 1.0)
            step = p1 / derivative
            z -= step
            if abs(step) < 2e-15:
                break
        else:
            raise ArithmeticError("Gauss-Legendre root did not converge")
        p0, p1 = 1.0, z
        for degree in range(2, order + 1):
            p0, p1 = p1, ((2 * degree - 1) * z * p1 - (degree - 1) * p0) / degree
        derivative = order * (z * p1 - p0) / (z * z - 1.0)
        weight = 2.0 / ((1.0 - z * z) * derivative * derivative)
        nodes[i], nodes[order - 1 - i] = -z, z
        weights[i] = weights[order - 1 - i] = weight
    return nodes, weights


def rectangular_segment_self_inductance(
    length_m: float, width_m: float, height_m: float, order: int = 128
) -> float:
    """Return the segment's Neumann self term in henries.

    The axial coordinate integral is analytic:
      I(rho) = l*asinh(l/rho) - sqrt(l*l + rho*rho) + rho.
    The remaining expectation is over the difference of two uniform points
    in the rectangular cross-section, whose density is
      4*(w-x)*(h-y)/(w*w*h*h).
    """
    values = (length_m, width_m, height_m)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("segment dimensions must be finite")
    if any(value <= 0.0 for value in values):
        raise ValueError("segment dimensions must be positive")
    if order < 8 or order > 512:
        raise ValueError("quadrature order must be between 8 and 512")

    nodes, weights = _gauss_legendre(order)
    xs = [(node + 1.0) * width_m / 2.0 for node in nodes]
    ys = [(node + 1.0) * height_m / 2.0 for node in nodes]
    wx = [weight * width_m / 2.0 for weight in weights]
    wy = [weight * height_m / 2.0 for weight in weights]

    weighted_integral = 0.0
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            rho = math.hypot(x, y)
            axial_integral = (
                length_m * math.asinh(length_m / rho)
                - math.hypot(length_m, rho)
                + rho
            )
            weighted_integral += (
                wx[i] * wy[j] * (width_m - x) * (height_m - y)
                * axial_integral
            )

    expectation = 4.0 * weighted_integral / (
        width_m * width_m * height_m * height_m
    )
    return MU0 / (2.0 * math.pi) * expectation
