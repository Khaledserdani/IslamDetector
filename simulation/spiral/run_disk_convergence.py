"""Run angular/radial convergence and inductance-matrix conditioning sweeps.

All targets are synthetic software fixtures. No result here is a field-depth
prediction or a substitute for measured target properties.
"""
from __future__ import annotations

import csv
from pathlib import Path

from mono_spiral_disk import (
    Coil, ConductiveDisk, Pulse, _solve, build_disk_model, receive_peak, simulate,
)


def matrix_condition_inf(matrix: list[list[float]]) -> float:
    """Compute ||L||_inf * ||inv(L)||_inf for this small dense matrix."""
    n = len(matrix)
    inverse_columns = []
    for column in range(n):
        unit = [0.0] * n
        unit[column] = 1.0
        inverse_columns.append(_solve(matrix, unit))
    inverse = [
        [inverse_columns[column][row] for column in range(n)]
        for row in range(n)
    ]
    norm_matrix = max(sum(abs(value) for value in row) for row in matrix)
    norm_inverse = max(sum(abs(value) for value in row) for row in inverse)
    return norm_matrix * norm_inverse


def evaluate(rings: int, segments: int) -> tuple[float, float]:
    # Synthetic software fixture only; not a user-selected or measured target.
    coil = Coil()
    disk = ConductiveDisk(
        radius_m=0.012,
        thickness_m=0.001,
        conductivity_s_m=35e6,
        depth_m=0.04,
        rings=rings,
    )
    inductance_matrix, _, _ = build_disk_model(coil, disk, ring_segments=segments)
    condition = matrix_condition_inf(inductance_matrix)
    peak = receive_peak(simulate(
        coil, disk, Pulse(time_step_s=1.0e-6), ring_segments=segments
    ))
    return peak, condition


def main() -> None:
    rows = []
    sweeps = [
        ("angular", [(6, 48), (6, 64), (6, 96), (6, 128)]),
        ("radial", [(3, 96), (4, 96), (5, 96), (6, 96),
                    (7, 96), (8, 96)]),
    ]
    for sweep_name, cases in sweeps:
        previous = None
        for rings, segments in cases:
            peak, condition = evaluate(rings, segments)
            relative_change = (
                None if previous is None
                else abs(peak - previous) / max(abs(peak), 1e-30)
            )
            row = {
                "sweep": sweep_name,
                "rings": rings,
                "segments_per_ring": segments,
                "coil_path": "canonical_continuous_mono_spiral",
                "receive_peak_v": f"{peak:.12e}",
                "relative_change_from_previous": (
                    "" if relative_change is None else f"{relative_change:.8g}"
                ),
                "inductance_matrix_condition_inf": f"{condition:.8g}",
                "fixture_only": "true",
            }
            rows.append(row)
            print(row)
            previous = peak

    output = Path("disk_surrogate_convergence_corrected.csv")
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
