"""Path-specific quasi-static inductance estimate for a round-wire Mono Spiral.

Implements a Greenhouse-style series-path sum:
    L = sum(L_self) + 2 * sum_{i<j}(signed M_ij)

The active square spiral is planar and axis-aligned. Connected collinear
pieces are merged before self terms are evaluated. Parallel-segment mutual
terms use the finite-length Neumann integral averaged over both circular wire
cross-sections with uniform current density. Perpendicular ideal straight
segments have zero Neumann dot-product term.

This is a DC/uniform-current geometric estimate, not a PI-frequency impedance
model, a measurement, or a substitute for skin/proximity and lead modelling.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from mono_spiral_geometry import MonoSpiral

MU0 = 4.0 * math.pi * 1e-7
Point3 = tuple[float, float, float]
Segment3 = tuple[Point3, Point3]


@dataclass(frozen=True)
class InductanceReport:
    inductance_h: float
    self_sum_h: float
    mutual_positive_h: float
    mutual_negative_h: float
    segment_count: int
    parallel_pair_count: int
    perpendicular_pair_count: int
    path_length_m: float
    wire_radius_m: float
    radial_order: int
    angular_order: int


def _vector(a: Point3, b: Point3) -> Point3:
    return (b[0] - a[0], b[1] - a[1], b[2] - a[2])


def _dot(a: Point3, b: Point3) -> float:
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


def _norm(a: Point3) -> float:
    return math.sqrt(_dot(a, a))


def _cross_norm(a: Point3, b: Point3) -> float:
    return math.sqrt(
        (a[1]*b[2] - a[2]*b[1])**2
        + (a[2]*b[0] - a[0]*b[2])**2
        + (a[0]*b[1] - a[1]*b[0])**2
    )


def _distance(a: Point3, b: Point3) -> float:
    return _norm(_vector(a, b))


def merge_collinear_segments(
    segments: Iterable[Segment3], tolerance: float = 1e-12
) -> tuple[Segment3, ...]:
    """Merge only contiguous, collinear pieces carrying current the same way."""
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    merged: list[Segment3] = []
    for start, end in segments:
        if _distance(start, end) <= tolerance:
            raise ValueError("zero-length conductor segment")
        if merged:
            previous_start, previous_end = merged[-1]
            first = _vector(previous_start, previous_end)
            second = _vector(start, end)
            if (
                _distance(previous_end, start) <= tolerance
                and _cross_norm(first, second)
                <= tolerance * _norm(first) * _norm(second)
                and _dot(first, second) > 0.0
            ):
                merged[-1] = (previous_start, end)
                continue
        merged.append((start, end))
    return tuple(merged)


def round_wire_segment_self_inductance_h(length_m: float, radius_m: float) -> float:
    """Rosa-Grover finite straight-wire partial self term, uniform DC current."""
    if not math.isfinite(length_m) or not math.isfinite(radius_m):
        raise ValueError("length and radius must be finite")
    if length_m <= 0.0 or radius_m <= 0.0:
        raise ValueError("length and radius must be positive")
    root = math.hypot(length_m, radius_m)
    bracket = (
        math.log((length_m + root) / radius_m)
        - root / length_m
        + 0.25
        + radius_m / length_m
    )
    return MU0 * length_m / (2.0 * math.pi) * bracket


def _gauss_legendre_unit_interval(order: int) -> tuple[tuple[float, float], ...]:
    """Return (node, weight) pairs on [0,1], using Newton-refined Legendre roots."""
    if not isinstance(order, int) or order < 1 or order > 32:
        raise ValueError("radial_order must be an integer from 1 to 32")
    result: list[tuple[float, float]] = []
    for index in range(1, order + 1):
        root = math.cos(math.pi * (index - 0.25) / (order + 0.5))
        for _ in range(64):
            p0, p1 = 1.0, root
            if order == 1:
                p1 = root
            else:
                for degree in range(2, order + 1):
                    p0, p1 = p1, (
                        (2.0 * degree - 1.0) * root * p1
                        - (degree - 1.0) * p0
                    ) / degree
            derivative = order * (root * p1 - p0) / (root * root - 1.0)
            step = p1 / derivative
            root -= step
            if abs(step) < 2e-15:
                break
        p0, p1 = 1.0, root
        if order > 1:
            for degree in range(2, order + 1):
                p0, p1 = p1, (
                    (2.0 * degree - 1.0) * root * p1
                    - (degree - 1.0) * p0
                ) / degree
        derivative = order * (root * p1 - p0) / (root * root - 1.0)
        weight = 1.0 / ((1.0 - root * root) * derivative * derivative)
        result.append(((root + 1.0) * 0.5, weight))
    return tuple(sorted(result))


def _uniform_disk_quadrature(
    radius_m: float, radial_order: int, angular_order: int
) -> tuple[tuple[float, float, float], ...]:
    """Area-normalized quadrature points (x,y,weight) in a circular cross-section."""
    if not math.isfinite(radius_m) or radius_m <= 0.0:
        raise ValueError("wire radius must be finite and positive")
    if not isinstance(angular_order, int) or angular_order < 8 or angular_order % 2:
        raise ValueError("angular_order must be an even integer >= 8")
    radial = _gauss_legendre_unit_interval(radial_order)
    points = []
    for t, radial_weight in radial:
        rho = radius_m * math.sqrt(t)
        for angle_index in range(angular_order):
            angle = 2.0 * math.pi * angle_index / angular_order
            points.append((
                rho * math.cos(angle),
                rho * math.sin(angle),
                radial_weight / angular_order,
            ))
    return tuple(points)


def _h_antiderivative(x: float, separation_m: float) -> float:
    return x * math.asinh(x / separation_m) - math.hypot(x, separation_m)


def parallel_segment_mutual_inductance_h(
    segment_a: Segment3,
    segment_b: Segment3,
    wire_radius_m: float,
    *,
    radial_order: int = 4,
    angular_order: int = 16,
) -> float:
    """Finite-length Neumann mutual term averaged over two round wire sections.

    Both segments must be parallel and non-overlapping in cross-section. Their
    actual endpoint directions determine the mutual sign. The circular-section
    average assumes uniform current density and is not a high-frequency model.
    """
    if not math.isfinite(wire_radius_m) or wire_radius_m <= 0.0:
        raise ValueError("wire_radius_m must be finite and positive")
    da = _vector(*segment_a)
    db = _vector(*segment_b)
    length_a, length_b = _norm(da), _norm(db)
    if length_a <= 0.0 or length_b <= 0.0:
        raise ValueError("segments must have positive length")
    ua = tuple(value / length_a for value in da)
    ub = tuple(value / length_b for value in db)
    direction_dot = _dot(ua, ub)
    if abs(abs(direction_dot) - 1.0) > 1e-10:
        raise ValueError("segments must be parallel")
    direction_sign = 1.0 if direction_dot > 0.0 else -1.0
    axis = ua

    # The Mono Spiral lies in XY, so these bases span each round cross-section.
    if abs(axis[0]) >= abs(axis[1]):
        basis_1: Point3 = (0.0, 1.0, 0.0)
    else:
        basis_1 = (1.0, 0.0, 0.0)
    basis_2: Point3 = (0.0, 0.0, 1.0)

    delta = _vector(segment_a[0], segment_b[0])
    axial_delta = _dot(delta, axis)
    perpendicular = tuple(delta[i] - axial_delta * axis[i] for i in range(3))
    center_separation = _norm(perpendicular)
    if center_separation <= 2.0 * wire_radius_m:
        raise ValueError("parallel wire cross-sections overlap or touch")

    a_interval = sorted((_dot(segment_a[0], axis), _dot(segment_a[1], axis)))
    b_interval = sorted((_dot(segment_b[0], axis), _dot(segment_b[1], axis)))
    a_points = _uniform_disk_quadrature(wire_radius_m, radial_order, angular_order)
    b_points = a_points
    r1 = _dot(perpendicular, basis_1)
    r2 = _dot(perpendicular, basis_2)
    weighted_integral = 0.0

    for x1, y1, w1 in a_points:
        for x2, y2, w2 in b_points:
            separation = math.hypot(r1 + x2 - x1, r2 + y2 - y1)
            if separation <= 0.0:
                raise ValueError("coincident cross-section quadrature points")
            integral = (
                _h_antiderivative(a_interval[1] - b_interval[0], separation)
                - _h_antiderivative(a_interval[0] - b_interval[0], separation)
                - _h_antiderivative(a_interval[1] - b_interval[1], separation)
                + _h_antiderivative(a_interval[0] - b_interval[1], separation)
            )
            weighted_integral += w1 * w2 * integral

    return direction_sign * MU0 / (4.0 * math.pi) * weighted_integral


def calculate_mono_spiral_inductance(
    geometry: MonoSpiral | None = None,
    *,
    wire_diameter_m: float | None = None,
    radial_order: int = 4,
    angular_order: int = 16,
) -> InductanceReport:
    """Calculate the series-path partial inductance of the active square spiral."""
    geometry = geometry or MonoSpiral()
    diameter = geometry.wire_diameter_m if wire_diameter_m is None else wire_diameter_m
    if not math.isfinite(diameter) or diameter <= 0.0:
        raise ValueError("wire_diameter_m must be finite and positive")
    if radial_order < 1 or radial_order > 32:
        raise ValueError("radial_order must be from 1 to 32")
    if angular_order < 8 or angular_order % 2:
        raise ValueError("angular_order must be an even integer >= 8")

    raw_segments = geometry.continuous_spiral_segments()
    segments = merge_collinear_segments(raw_segments)
    radius = diameter / 2.0
    path_length = sum(_distance(start, end) for start, end in segments)
    raw_length = sum(_distance(start, end) for start, end in raw_segments)
    if abs(path_length - raw_length) > 1e-10:
        raise ArithmeticError("collinear merging changed the conductor path length")

    self_sum = sum(
        round_wire_segment_self_inductance_h(_distance(start, end), radius)
        for start, end in segments
    )
    positive = 0.0
    negative = 0.0
    parallel_count = 0
    perpendicular_count = 0

    for index, first in enumerate(segments):
        first_vector = _vector(*first)
        first_length = _norm(first_vector)
        first_unit = tuple(value / first_length for value in first_vector)
        for second in segments[index + 1:]:
            second_vector = _vector(*second)
            second_length = _norm(second_vector)
            second_unit = tuple(value / second_length for value in second_vector)
            direction_dot = _dot(first_unit, second_unit)
            if abs(abs(direction_dot) - 1.0) <= 1e-10:
                mutual = parallel_segment_mutual_inductance_h(
                    first,
                    second,
                    radius,
                    radial_order=radial_order,
                    angular_order=angular_order,
                )
                parallel_count += 1
                if mutual >= 0.0:
                    positive += mutual
                else:
                    negative += mutual
            elif abs(direction_dot) <= 1e-10:
                perpendicular_count += 1
            else:
                raise ValueError("only parallel or perpendicular segments are supported")

    total = self_sum + 2.0 * (positive + negative)
    if not math.isfinite(total) or total <= 0.0:
        raise ArithmeticError("computed series-path inductance is not positive and finite")
    return InductanceReport(
        inductance_h=total,
        self_sum_h=self_sum,
        mutual_positive_h=positive,
        mutual_negative_h=negative,
        segment_count=len(segments),
        parallel_pair_count=parallel_count,
        perpendicular_pair_count=perpendicular_count,
        path_length_m=path_length,
        wire_radius_m=radius,
        radial_order=radial_order,
        angular_order=angular_order,
    )
