#!/usr/bin/env python3
"""First-principles magnetostatic filament kernel for supplied 3D wire paths."""
from __future__ import annotations
import math
from typing import Iterable
import numpy as np

MU0 = 4.0e-7 * math.pi

def _closed_segments(path: Iterable[Iterable[float]], name: str):
    points = np.asarray(list(path), dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 4:
        raise ValueError(f"{name}: expected at least four 3D vertices")
    if not np.isfinite(points).all():
        raise ValueError(f"{name}: coordinates must be finite")
    if np.linalg.norm(points[0] - points[-1]) > 1e-9:
        points = np.vstack((points, points[0]))
    dl = np.diff(points, axis=0)
    if np.any(np.linalg.norm(dl, axis=1) <= 1e-12):
        raise ValueError(f"{name}: zero-length wire segment")
    return points[:-1], dl

def path_length_m(path_m):
    """Total centerline length [m] of one closed winding path."""
    starts, dl = _closed_segments(path_m, "coil")
    return float(np.sum(np.linalg.norm(dl, axis=1)))

def field_at_points(path_m, points_m, current_a=1.0, turns=1, point_batch=64):
    """B [T] at observation points using midpoint Biot-Savart quadrature."""
    if not math.isfinite(current_a) or not isinstance(turns, int) or turns < 1:
        raise ValueError("current must be finite and turns a positive integer")
    if point_batch < 1:
        raise ValueError("point_batch must be positive")
    starts, dl = _closed_segments(path_m, "coil")
    mid = starts + 0.5 * dl
    obs = np.asarray(list(points_m), dtype=float)
    if obs.ndim == 1:
        obs = obs.reshape(1, 3)
    if obs.ndim != 2 or obs.shape[1] != 3 or not np.isfinite(obs).all():
        raise ValueError("observation points must be finite Nx3 coordinates")
    result = np.empty((len(obs), 3), dtype=float)
    scale = MU0 * current_a * turns / (4.0 * math.pi)
    for first in range(0, len(obs), point_batch):
        batch = obs[first:first + point_batch]
        r = batch[:, None, :] - mid[None, :, :]
        distance = np.linalg.norm(r, axis=2)
        if np.any(distance <= 1e-10):
            raise ValueError("field is singular at a wire-segment midpoint")
        terms = np.cross(dl[None, :, :], r) / distance[:, :, None] ** 3
        result[first:first + len(batch)] = scale * np.sum(terms, axis=1)
    return result

def mutual_inductance(path_a_m, path_b_m, turns_a=1, turns_b=1, segment_batch=128):
    """Signed Neumann mutual inductance [H] for two distinct filament loops."""
    if not isinstance(turns_a, int) or turns_a < 1 or not isinstance(turns_b, int) or turns_b < 1:
        raise ValueError("turn counts must be positive integers")
    if segment_batch < 1:
        raise ValueError("segment_batch must be positive")
    starts_a, dl_a = _closed_segments(path_a_m, "coil A")
    starts_b, dl_b = _closed_segments(path_b_m, "coil B")
    mid_a, mid_b = starts_a + 0.5 * dl_a, starts_b + 0.5 * dl_b
    total = 0.0
    for first in range(0, len(mid_a), segment_batch):
        ma, da = mid_a[first:first + segment_batch], dl_a[first:first + segment_batch]
        delta = ma[:, None, :] - mid_b[None, :, :]
        distance = np.linalg.norm(delta, axis=2)
        if np.any(distance <= 1e-9):
            raise ValueError("filament paths intersect or approach within 1 nm")
        dot = np.einsum("ik,jk->ij", da, dl_b)
        total += float(np.sum(dot / distance))
    return MU0 * turns_a * turns_b * total / (4.0 * math.pi)


def flux_through_loop(source_path_m, receiver_path_m, current_a=1.0, source_turns=1, subdivisions=16):
    """Integrate source B·dA over one planar, convex receiver loop [Wb/turn]."""
    if not math.isfinite(current_a):
        raise ValueError("current_a must be finite")
    if not isinstance(source_turns, int) or source_turns < 1:
        raise ValueError("source_turns must be a positive integer")
    if not isinstance(subdivisions, int) or subdivisions < 1:
        raise ValueError("subdivisions must be a positive integer")

    receiver = np.asarray(list(receiver_path_m), dtype=float)
    if receiver.ndim != 2 or receiver.shape[1] != 3 or len(receiver) < 4 or not np.isfinite(receiver).all():
        raise ValueError("receiver loop must contain at least four finite 3D vertices")
    if np.linalg.norm(receiver[0] - receiver[-1]) <= 1e-9:
        receiver = receiver[:-1]
    if len(receiver) < 3:
        raise ValueError("receiver loop must contain at least three distinct vertices")

    span = float(np.linalg.norm(np.ptp(receiver, axis=0)))
    if not math.isfinite(span) or span <= 1e-12:
        raise ValueError("receiver surface is degenerate")
    area_vector = 0.5 * np.sum(np.cross(receiver, np.roll(receiver, -1, axis=0)), axis=0)
    area = float(np.linalg.norm(area_vector))
    if not math.isfinite(area) or area <= 1e-14 * span * span:
        raise ValueError("receiver surface has zero or indeterminate area")
    normal = area_vector / area
    plane_error = float(np.max(np.abs((receiver - receiver[0]) @ normal)))
    if plane_error > 1e-7 * span:
        raise ValueError("receiver loop must be planar for surface-flux integration")

    edges = np.roll(receiver, -1, axis=0) - receiver
    edge_lengths = np.linalg.norm(edges, axis=1)
    if np.any(edge_lengths <= 1e-12 * span):
        raise ValueError("receiver polygon contains a zero-length edge")

    # Project the planar polygon to 2D and reject crossings between
    # non-adjacent edges before using a triangle fan.
    basis_u = edges[0] / edge_lengths[0]
    basis_v = np.cross(normal, basis_u)
    projected = np.column_stack(((receiver - receiver[0]) @ basis_u,
                                 (receiver - receiver[0]) @ basis_v))
    intersection_tolerance = 1e-12 * span * span
    coordinate_tolerance = 1e-12 * span

    def orient2(a, b, c):
        ab, ac = b - a, c - a
        return float(ab[0] * ac[1] - ab[1] * ac[0])

    def on_segment(a, b, q):
        return (min(a[0], b[0]) - coordinate_tolerance <= q[0] <= max(a[0], b[0]) + coordinate_tolerance
                and min(a[1], b[1]) - coordinate_tolerance <= q[1] <= max(a[1], b[1]) + coordinate_tolerance)

    count = len(projected)
    for i in range(count):
        a, b = projected[i], projected[(i + 1) % count]
        for j in range(i + 1, count):
            if j == i or j == (i + 1) % count or i == (j + 1) % count:
                continue
            c, d = projected[j], projected[(j + 1) % count]
            o1, o2 = orient2(a, b, c), orient2(a, b, d)
            o3, o4 = orient2(c, d, a), orient2(c, d, b)
            proper = ((o1 > intersection_tolerance and o2 < -intersection_tolerance)
                      or (o1 < -intersection_tolerance and o2 > intersection_tolerance)) and (
                      (o3 > intersection_tolerance and o4 < -intersection_tolerance)
                      or (o3 < -intersection_tolerance and o4 > intersection_tolerance))
            touching = (
                (abs(o1) <= intersection_tolerance and on_segment(a, b, c))
                or (abs(o2) <= intersection_tolerance and on_segment(a, b, d))
                or (abs(o3) <= intersection_tolerance and on_segment(c, d, a))
                or (abs(o4) <= intersection_tolerance and on_segment(c, d, b))
            )
            if proper or touching:
                raise ValueError("receiver polygon must be a simple, non-self-intersecting loop")

    turns = np.einsum("ij,j->i", np.cross(edges, np.roll(edges, -1, axis=0)), normal)
    convexity_tolerance = 1e-12 * span * span
    if np.any(turns < -convexity_tolerance):
        raise ValueError("receiver polygon must be convex for fan triangulation")
    triangle_count = (len(receiver) - 2) * subdivisions * subdivisions
    if triangle_count > 500000:
        raise ValueError("surface integration exceeds 500,000 subtriangles")

    centroids = []
    area_vectors = []
    anchor = receiver[0]
    for index in range(1, len(receiver) - 1):
        b, c = receiver[index], receiver[index + 1]
        for i in range(subdivisions):
            for j in range(subdivisions - i):
                coords = np.asarray(((i, j), (i + 1, j), (i, j + 1)), dtype=float) / subdivisions
                weights = np.column_stack((1.0 - np.sum(coords, axis=1), coords))
                vertices = (weights[:, 0, None] * anchor
                            + weights[:, 1, None] * b
                            + weights[:, 2, None] * c)
                centroids.append(np.mean(vertices, axis=0))
                area_vectors.append(0.5 * np.cross(vertices[1] - vertices[0], vertices[2] - vertices[0]))
                if i + j < subdivisions - 1:
                    coords = np.asarray(((i + 1, j), (i + 1, j + 1), (i, j + 1)), dtype=float) / subdivisions
                    weights = np.column_stack((1.0 - np.sum(coords, axis=1), coords))
                    vertices = (weights[:, 0, None] * anchor
                                + weights[:, 1, None] * b
                                + weights[:, 2, None] * c)
                    centroids.append(np.mean(vertices, axis=0))
                    area_vectors.append(0.5 * np.cross(vertices[1] - vertices[0], vertices[2] - vertices[0]))

    magnetic_field = field_at_points(source_path_m, centroids, current_a=current_a, turns=source_turns)
    return float(np.einsum("ij,ij->", magnetic_field, np.asarray(area_vectors)))


def flux_linkage(source_path_m, receiver_path_m, current_a=1.0,
                 source_turns=1, receiver_turns=1, subdivisions=16):
    """Total receiver flux linkage [Wb-turn] from the source loop field."""
    if not isinstance(receiver_turns, int) or receiver_turns < 1:
        raise ValueError("receiver_turns must be a positive integer")
    return receiver_turns * flux_through_loop(
        source_path_m, receiver_path_m, current_a=current_a,
        source_turns=source_turns, subdivisions=subdivisions
    )

def circular_loop(radius_m, segments=512, z_m=0.0):
    """Closed CCW circular centerline for analytical verification."""
    if not math.isfinite(radius_m) or radius_m <= 0 or segments < 16:
        raise ValueError("radius must be positive and segments >= 16")
    theta = np.linspace(0.0, 2.0 * math.pi, segments + 1)
    return np.column_stack((radius_m*np.cos(theta), radius_m*np.sin(theta), np.full(segments+1, z_m)))

def circular_loop_axis_field(radius_m, z_m, current_a=1.0, turns=1):
    """Analytical axial magnetic flux density of a circular loop [T]."""
    if radius_m <= 0 or turns < 1 or not all(map(math.isfinite, (radius_m, z_m, current_a))):
        raise ValueError("invalid circular-loop parameters")
    return MU0 * turns * current_a * radius_m**2 / (2.0 * (radius_m**2 + z_m**2)**1.5)
