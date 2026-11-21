"""Geometric-mean-distance diagnostics for rectangular conductor sections.

This module evaluates the logarithmic-kernel GMD of a uniformly filled
rectangular cross-section. It is a geometry primitive only: it is NOT a
complete loop self-inductance formula and does not include internal magnetic
energy, finite-loop curvature, neighboring conductors, or frequency effects.
"""
from __future__ import annotations

import math


def _gauss_legendre(order: int) -> tuple[list[float], list[float]]:
    """Return nodes and weights on [-1, 1] using Newton iteration."""
    if order < 2:
        raise ValueError("quadrature order must be at least 2")
    nodes = [0.0] * order
    weights = [0.0] * order
    half = (order + 1) // 2
    for i in range(half):
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


def rectangular_cross_section_gmd(width_m: float, height_m: float,
                                  order: int = 96) -> float:
    """Return exp(E[ln(distance)]) for two independent uniform points.

    The expectation is evaluated through the difference-coordinate density:
    4*(w-x)*(h-y)/(w*h)^2 over x in [0,w], y in [0,h].
    The result scales linearly with either common length scale.
    """
    if not math.isfinite(width_m) or not math.isfinite(height_m):
        raise ValueError("cross-section dimensions must be finite")
    if width_m <= 0.0 or height_m <= 0.0:
        raise ValueError("cross-section dimensions must be positive")
    if order < 8 or order > 512:
        raise ValueError("quadrature order must be between 8 and 512")

    nodes, weights = _gauss_legendre(order)
    x_values = [(node + 1.0) * width_m / 2.0 for node in nodes]
    y_values = [(node + 1.0) * height_m / 2.0 for node in nodes]
    x_weights = [weight * width_m / 2.0 for weight in weights]
    y_weights = [weight * height_m / 2.0 for weight in weights]

    weighted_log_distance = 0.0
    for i, x in enumerate(x_values):
        x_density = width_m - x
        for j, y in enumerate(y_values):
            distance = math.hypot(x, y)
            weighted_log_distance += (
                x_weights[i] * y_weights[j] * x_density * (height_m - y)
                * math.log(distance)
            )
    mean_log_distance = 4.0 * weighted_log_distance / (
        width_m * width_m * height_m * height_m
    )
    return math.exp(mean_log_distance)
