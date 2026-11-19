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

def rectangular_adjacent_segment_mutual_inductance(
    length_a_m: float, length_b_m: float,
    width_m: float, height_m: float, order: int = 128
) -> float:
    """Return mutual inductance of two contiguous collinear segments.

    Both segments carry current in the same axial direction, meet end-to-end,
    and have the same uniformly filled rectangular cross-section. This special
    case avoids the zero-separation singularity of a filament formula.
    """
    values = (length_a_m, length_b_m, width_m, height_m)
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

            def primitive(value: float) -> float:
                return value * math.asinh(value / rho) - math.hypot(value, rho)

            integral = (
                primitive(length_a_m + length_b_m)
                - primitive(length_a_m)
                - primitive(length_b_m)
                + primitive(0.0)
            )
            weighted_integral += (
                wx[i] * wy[j] * (width_m - x) * (height_m - y) * integral
            )

    expectation = 4.0 * weighted_integral / (
        width_m * width_m * height_m * height_m
    )
    return MU0 / (4.0 * math.pi) * expectation

def rectangular_parallel_segment_mutual_inductance(
    length_a_m: float,
    length_b_m: float,
    width_m: float,
    height_m: float,
    transverse_offset_x_m: float = 0.0,
    transverse_offset_y_m: float = 0.0,
    axial_offset_m: float = 0.0,
    order: int = 96,
) -> float:
    """Mutual inductance of two parallel, equally oriented rectangular wires.

    Segment A occupies z=[0, length_a]. Segment B occupies
    z=[axial_offset, axial_offset+length_b] and its cross-section center is
    shifted by (transverse_offset_x, transverse_offset_y). Both conductors
    have the same rectangular section and uniform axial current density.

    The axial Neumann double integral is analytic. The remaining expectation
    is over the difference of two independent uniform points in each section.
    This handles separated parallel segments and the contiguous collinear
    special case without a filament self-singularity.
    """
    values = (
        length_a_m, length_b_m, width_m, height_m,
        transverse_offset_x_m, transverse_offset_y_m, axial_offset_m,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("segment dimensions and offsets must be finite")
    if min(length_a_m, length_b_m, width_m, height_m) <= 0.0:
        raise ValueError("segment dimensions must be positive")
    if order < 8 or order > 512:
        raise ValueError("quadrature order must be between 8 and 512")

    nodes, weights = _gauss_legendre(order)
    differences_x = [node * width_m for node in nodes]
    differences_y = [node * height_m for node in nodes]
    density_weights_x = [
        weight * (width_m - abs(value)) / width_m
        for value, weight in zip(differences_x, weights)
    ]
    density_weights_y = [
        weight * (height_m - abs(value)) / height_m
        for value, weight in zip(differences_y, weights)
    ]

    def second_primitive(value: float, rho: float) -> float:
        if rho == 0.0:
            if value == 0.0:
                return 0.0
            return value * (math.log(2.0 * abs(value)) - 1.0)
        return value * math.asinh(value / rho) - math.hypot(value, rho)

    c = axial_offset_m
    a = length_a_m
    b = length_b_m
    weighted_integral = 0.0
    for i, dx in enumerate(differences_x):
        for j, dy in enumerate(differences_y):
            rho = math.hypot(
                dx + transverse_offset_x_m,
                dy + transverse_offset_y_m,
            )
            if rho <= 1e-15 * max(width_m, height_m):
                # An exact quadrature hit on the integrable cross-section
                # singularity is not a valid point sample.
                raise ArithmeticError(
                    "quadrature node hit the cross-section singularity; "
                    "change quadrature order or offset"
                )
            integral = (
                second_primitive(a - c, rho)
                - second_primitive(-c, rho)
                - second_primitive(a - c - b, rho)
                + second_primitive(-c - b, rho)
            )
            weighted_integral += (
                density_weights_x[i] * density_weights_y[j] * integral
            )

    return MU0 / (4.0 * math.pi) * weighted_integral

