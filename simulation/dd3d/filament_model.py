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
