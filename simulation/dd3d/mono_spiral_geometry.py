#!/usr/bin/env python3
"""Parametric Mono Spiral PI centerline geometry candidates.

The generator emits one continuous open conductor path. It does not estimate
self-inductance, target response, soil response, or detection depth.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import numpy as np


def _positive(name, value):
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and > 0")


def rounded_rectangle_loop(width_m, height_m, corner_radius_m, arc_step_deg=2.0):
    """CCW rounded-rectangle centerline, starting/ending at right-edge midpoint."""
    for name, value in (("width_m", width_m), ("height_m", height_m),
                        ("arc_step_deg", arc_step_deg)):
        _positive(name, value)
    if not math.isfinite(corner_radius_m) or corner_radius_m < 0:
        raise ValueError("corner_radius_m must be finite and >= 0")
    if 2 * corner_radius_m > min(width_m, height_m):
        raise ValueError("corner radius does not fit the rectangle")
    if arc_step_deg > 45:
        raise ValueError("arc_step_deg must be <= 45 degrees")

    if corner_radius_m == 0:
        # Four sharp corners; start at the midpoint of the right edge.
        return np.asarray([
            [width_m / 2, 0.0, 0.0],
            [width_m / 2, height_m / 2, 0.0],
            [-width_m / 2, height_m / 2, 0.0],
            [-width_m / 2, -height_m / 2, 0.0],
            [width_m / 2, -height_m / 2, 0.0],
            [width_m / 2, 0.0, 0.0],
        ], dtype=float)

    r = corner_radius_m
    corners = [
        (width_m / 2 - r, height_m / 2 - r, 0.0, 90.0),
        (-width_m / 2 + r, height_m / 2 - r, 90.0, 180.0),
        (-width_m / 2 + r, -height_m / 2 + r, 180.0, 270.0),
        (width_m / 2 - r, -height_m / 2 + r, 270.0, 360.0),
    ]
    points = [[width_m / 2, 0.0, 0.0],
              [width_m / 2, height_m / 2 - r, 0.0]]
    for cx, cy, start, end in corners:
        count = max(2, int(math.ceil((end - start) / arc_step_deg)))
        angles = np.linspace(math.radians(start), math.radians(end), count + 1)
        arc = [[cx + r * math.cos(a), cy + r * math.sin(a), 0.0] for a in angles]
        # Skip first point when it duplicates the previous straight segment end.
        points.extend(arc[1:])
        if end == 90.0:
            points.append([-width_m / 2 + r, height_m / 2, 0.0])
        elif end == 180.0:
            points.append([-width_m / 2, -height_m / 2 + r, 0.0])
        elif end == 270.0:
            points.append([width_m / 2 - r, -height_m / 2, 0.0])
        elif end == 360.0:
            points.append([width_m / 2, 0.0, 0.0])
    # Remove duplicate consecutive vertices introduced at tangent joins.
    cleaned = [points[0]]
    for point in points[1:]:
        if np.linalg.norm(np.asarray(point) - np.asarray(cleaned[-1])) > 1e-12:
            cleaned.append(point)
    if np.linalg.norm(np.asarray(cleaned[0]) - np.asarray(cleaned[-1])) > 1e-12:
        cleaned.append(cleaned[0])
    return np.asarray(cleaned, dtype=float)


def circular_loop_path(radius_m, arc_step_deg=2.0):
    _positive("radius_m", radius_m)
    _positive("arc_step_deg", arc_step_deg)
    if arc_step_deg > 45:
        raise ValueError("arc_step_deg must be <= 45 degrees")
    count = max(16, int(math.ceil(360.0 / arc_step_deg)))
    theta = np.linspace(0.0, 2.0 * math.pi, count + 1)
    return np.column_stack((radius_m * np.cos(theta),
                            radius_m * np.sin(theta),
                            np.zeros(count + 1)))


def build_spiral(family, turns, pitch_m, insulation_outer_diameter_m,
                 min_surface_clearance_m, arc_step_deg,
                 outer_width_m=None, outer_height_m=None,
                 outer_corner_radius_m=None, outer_radius_m=None):
    """Build a single continuous open spiral path and transparent geometry report.

    pitch_m is centerline-to-centerline offset. Adjacent turn clearance is
    pitch_m minus the insulated wire outside diameter.
    """
    if not isinstance(turns, int) or turns < 1:
        raise ValueError("turns must be a positive integer")
    _positive("pitch_m", pitch_m)
    _positive("insulation_outer_diameter_m", insulation_outer_diameter_m)
    if not math.isfinite(min_surface_clearance_m) or min_surface_clearance_m < 0:
        raise ValueError("min_surface_clearance_m must be finite and >= 0")
    actual_clearance = pitch_m - insulation_outer_diameter_m
    if actual_clearance + 1e-12 < min_surface_clearance_m:
        raise ValueError("adjacent insulated turns violate the specified clearance")

    loops = []
    per_turn = []
    if family == "rounded-square":
        if outer_width_m is None or outer_height_m is None or outer_corner_radius_m is None:
            raise ValueError("rounded-square requires outer width, height, and corner radius")
        _positive("outer_width_m", outer_width_m)
        _positive("outer_height_m", outer_height_m)
        if not math.isfinite(outer_corner_radius_m) or outer_corner_radius_m < 0:
            raise ValueError("outer_corner_radius_m must be finite and >= 0")
        for k in range(turns):
            w = outer_width_m - 2.0 * k * pitch_m
            h = outer_height_m - 2.0 * k * pitch_m
            r = outer_corner_radius_m - k * pitch_m
            if (w <= insulation_outer_diameter_m or h <= insulation_outer_diameter_m
                    or r < 0.0 or 2.0 * r > min(w, h)):
                raise ValueError(f"turn {k + 1} collapses or cannot contain the inward-offset corner radius")
            loop = rounded_rectangle_loop(w, h, r, arc_step_deg)
            loops.append(loop)
            per_turn.append({"turn": k + 1, "width_m": w, "height_m": h,
                             "corner_radius_m": r})
    elif family == "circle":
        if outer_radius_m is None:
            raise ValueError("circle requires outer radius")
        _positive("outer_radius_m", outer_radius_m)
        for k in range(turns):
            radius = outer_radius_m - k * pitch_m
            if radius <= insulation_outer_diameter_m / 2:
                raise ValueError(f"turn {k + 1} collapses")
            loops.append(circular_loop_path(radius, arc_step_deg))
            per_turn.append({"turn": k + 1, "radius_m": radius})
    else:
        raise ValueError("family must be 'circle' or 'rounded-square'")

    # Each loop starts and ends at its rightmost midpoint. The short radial
    # segment joins adjacent turns through the gap; no phantom closure is added.
    path = []
    for loop in loops:
        if not path:
            path.extend(loop.tolist())
        else:
            if np.linalg.norm(np.asarray(path[-1]) - loop[0]) <= 1e-12:
                raise ValueError("unexpected coincident turn endpoints")
            path.append(loop[0].tolist())  # explicit radial transition to the next turn
            path.extend(loop[1:].tolist())
    path_array = np.asarray(path, dtype=float)
    segment_lengths = np.linalg.norm(np.diff(path_array, axis=0), axis=1)
    if np.any(segment_lengths <= 1e-12):
        raise ValueError("generated path contains zero-length segments")
    turn_lengths = []
    for loop in loops:
        turn_lengths.append(float(np.sum(np.linalg.norm(np.diff(loop, axis=0), axis=1))))
    transition_lengths = [float(np.linalg.norm(loops[k + 1][0] - loops[k][-1]))
                          for k in range(turns - 1)]
    # The loop ends at its start; connectors are the segments between loop arrays.
    # Sum explicitly to avoid counting a closed-loop seam as copper transition.
    total_length = sum(turn_lengths) + sum(transition_lengths)
    return path_array, {
        "schema_version": 1,
        "family": family,
        "turns": turns,
        "pitch_centerline_m": pitch_m,
        "insulation_outer_diameter_m": insulation_outer_diameter_m,
        "minimum_surface_clearance_m": min_surface_clearance_m,
        "actual_nominal_surface_clearance_m": actual_clearance,
        "arc_step_deg": arc_step_deg,
        "per_turn": per_turn,
        "turn_lengths_m": turn_lengths,
        "transition_lengths_m": transition_lengths,
        "centerline_length_m": total_length,
        "path_vertices": int(len(path_array)),
        "path_is_open": True,
        "status": "GEOMETRY_CANDIDATE_NOT_MANUFACTURING_RELEASE",
        "limitations": [
            "lead/service lengths are not included",
            "wire bend-radius and insulation tolerances require supplier data",
            "self-inductance and target/soil response are not calculated",
            "turn-to-turn clearance is nominal and assumes ideal offset geometry"
        ]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", choices=("circle", "rounded-square"), required=True)
    parser.add_argument("--turns", type=int, required=True)
    parser.add_argument("--pitch-mm", type=float, required=True)
    parser.add_argument("--insulation-od-mm", type=float, required=True)
    parser.add_argument("--min-clearance-mm", type=float, required=True)
    parser.add_argument("--arc-step-deg", type=float, default=2.0)
    parser.add_argument("--outer-width-mm", type=float)
    parser.add_argument("--outer-height-mm", type=float)
    parser.add_argument("--outer-corner-radius-mm", type=float)
    parser.add_argument("--outer-radius-mm", type=float)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    path, report = build_spiral(
        args.family, args.turns, args.pitch_mm / 1000.0,
        args.insulation_od_mm / 1000.0, args.min_clearance_mm / 1000.0,
        args.arc_step_deg,
        outer_width_m=None if args.outer_width_mm is None else args.outer_width_mm / 1000.0,
        outer_height_m=None if args.outer_height_mm is None else args.outer_height_mm / 1000.0,
        outer_corner_radius_m=None if args.outer_corner_radius_mm is None else args.outer_corner_radius_mm / 1000.0,
        outer_radius_m=None if args.outer_radius_mm is None else args.outer_radius_mm / 1000.0,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    np.savetxt(args.out / "centerline_xyz_m.csv", path, delimiter=",",
               header="x_m,y_m,z_m", comments="")
    (args.out / "geometry_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "
", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
