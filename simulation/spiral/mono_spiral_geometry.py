"""Geometry and Biot-Savart reference model for the 35x35 cm Mono Spiral PI coil.

The conductor is represented as ONE continuous square spiral, including the
radial inter-turn transitions. This is a magnetostatic filament model only:
it does not model switching transients, target eddy currents, soil, RX loading,
or the external terminal leads.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

MU0 = 4.0 * math.pi * 1e-7
Point3 = tuple[float, float, float]
Segment3 = tuple[Point3, Point3]


@dataclass(frozen=True)
class MonoSpiral:
    outer_side_m: float = 0.350
    turns: int = 13
    pitch_m: float = 0.0012
    wire_diameter_m: float = 0.0006

    def __post_init__(self) -> None:
        if self.outer_side_m <= 0:
            raise ValueError("outer_side_m must be positive")
        if self.turns < 1:
            raise ValueError("turns must be at least one")
        if self.pitch_m <= 0:
            raise ValueError("pitch_m must be positive")
        if self.wire_diameter_m <= 0:
            raise ValueError("wire_diameter_m must be positive")
        if self.inner_side_m <= 0:
            raise ValueError("turns and pitch leave no positive inner opening")
        if self.pitch_m < self.wire_diameter_m:
            raise ValueError("pitch cannot be smaller than the wire diameter")

    @property
    def inner_side_m(self) -> float:
        return self.outer_side_m - 2.0 * self.pitch_m * (self.turns - 1)

    @property
    def clear_gap_m(self) -> float:
        return self.pitch_m - self.wire_diameter_m

    @property
    def turn_sides_m(self) -> tuple[float, ...]:
        return tuple(
            self.outer_side_m - 2.0 * self.pitch_m * index
            for index in range(self.turns)
        )

    @property
    def copper_path_length_m(self) -> float:
        # Each inward connector replaces an equal-length omitted part of the
        # preceding turn's fourth side, so the path equals the sum of perimeters.
        return 4.0 * sum(self.turn_sides_m)

    @property
    def copper_resistance_20c_ohm(self) -> float:
        copper_resistivity_ohm_m = 1.724e-8
        area_m2 = math.pi * (self.wire_diameter_m / 2.0) ** 2
        return copper_resistivity_ohm_m * self.copper_path_length_m / area_m2

    def continuous_spiral_segments(self) -> tuple[Segment3, ...]:
        """Return a continuous inward spiral, starting at the outer bottom-left.

        Each turn runs bottom -> right -> top -> down the left side to the next
        turn's lower-left corner, then uses a short radial connector to enter
        the next turn. The final turn closes at its lower-left corner.
        """
        halves = tuple(side / 2.0 for side in self.turn_sides_m)
        segments: list[Segment3] = []
        for index, half in enumerate(halves):
            bottom_left = (-half, -half, 0.0)
            bottom_right = (half, -half, 0.0)
            top_right = (half, half, 0.0)
            top_left = (-half, half, 0.0)
            next_y = -halves[index + 1] if index + 1 < len(halves) else -half
            left_end = (-half, next_y, 0.0)
            segments.extend((
                (bottom_left, bottom_right),
                (bottom_right, top_right),
                (top_right, top_left),
                (top_left, left_end),
            ))
            if index + 1 < len(halves):
                next_bottom_left = (-halves[index + 1], -halves[index + 1], 0.0)
                segments.append((left_end, next_bottom_left))
        return tuple(segments)

    def square_turn_segments(self) -> tuple[Segment3, ...]:
        """Return the former disconnected-loop idealization for comparison."""
        segments: list[Segment3] = []
        for side in self.turn_sides_m:
            half = side / 2.0
            corners = (
                (-half, -half, 0.0),
                (half, -half, 0.0),
                (half, half, 0.0),
                (-half, half, 0.0),
                (-half, -half, 0.0),
            )
            segments.extend(zip(corners[:-1], corners[1:]))
        return tuple(segments)

    def magnetic_field_tesla(
        self,
        point_m: Point3,
        current_a: float = 1.0,
        segments_per_side: int = 100,
    ) -> tuple[float, float, float]:
        """Return B=(Bx,By,Bz) by midpoint Biot-Savart integration."""
        if segments_per_side < 1:
            raise ValueError("segments_per_side must be positive")
        px, py, pz = point_m
        bx = by = bz = 0.0
        scale = MU0 * current_a / (4.0 * math.pi)

        for start, end in self.continuous_spiral_segments():
            dx = (end[0] - start[0]) / segments_per_side
            dy = (end[1] - start[1]) / segments_per_side
            dz = (end[2] - start[2]) / segments_per_side
            dl = (dx, dy, dz)
            for index in range(segments_per_side):
                sx = start[0] + (index + 0.5) * dx
                sy = start[1] + (index + 0.5) * dy
                sz = start[2] + (index + 0.5) * dz
                rx, ry, rz = px - sx, py - sy, pz - sz
                r2 = rx * rx + ry * ry + rz * rz
                if r2 == 0.0:
                    raise ValueError("field point lies on the ideal wire centreline")
                inv_r3 = 1.0 / (r2 * math.sqrt(r2))
                bx += scale * (dl[1] * rz - dl[2] * ry) * inv_r3
                by += scale * (dl[2] * rx - dl[0] * rz) * inv_r3
                bz += scale * (dl[0] * ry - dl[1] * rx) * inv_r3

        return bx, by, bz


def square_loop_center_field_tesla(side_m: float, current_a: float = 1.0) -> float:
    """Analytic Bz at the centre of one thin square loop."""
    if side_m <= 0:
        raise ValueError("side_m must be positive")
    return 2.0 * math.sqrt(2.0) * MU0 * current_a / (math.pi * side_m)
