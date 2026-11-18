"""Parameter sweep for synthetic conductive-disk fixtures.

This explores model sensitivity to target radius, thickness, conductivity,
depth and lateral offset. It is not a detector-depth claim and does not
represent measured objects.
"""
from __future__ import annotations

import csv
from pathlib import Path

from mono_spiral_disk import (
    Coil, ConductiveDisk, Pulse, _solve, build_disk_model, receive_peak, simulate,
)


def condition_inf(matrix: list[list[float]]) -> float:
    n = len(matrix)
    inv_cols = []
    for col in range(n):
        rhs = [0.0] * n
        rhs[col] = 1.0
        inv_cols.append(_solve(matrix, rhs))
    inverse = [[inv_cols[col][row] for col in range(n)] for row in range(n)]
    norm_a = max(sum(abs(x) for x in row) for row in matrix)
    norm_inv = max(sum(abs(x) for x in row) for row in inverse)
    return norm_a * norm_inv


def main() -> None:
    coil = Coil()
    pulse = Pulse(time_step_s=0.5e-6)
    cases = []
    for radius_mm in (6.0, 12.0, 20.0):
        cases.append(("radius", radius_mm, 1.0, 35e6, 40.0, 0.0))
    for thickness_mm in (0.25, 0.5, 1.0, 2.0):
        cases.append(("thickness", 12.0, thickness_mm, 35e6, 40.0, 0.0))
    for conductivity_ms_m in (5.8, 17.0, 35.0, 58.0):
        cases.append(("conductivity", 12.0, 1.0, conductivity_ms_m*1e6, 40.0, 0.0))
    for depth_mm in (20.0, 40.0, 60.0, 80.0, 100.0):
        cases.append(("depth", 12.0, 1.0, 35e6, depth_mm, 0.0))
    for offset_mm in (0.0, 20.0, 50.0, 100.0):
        cases.append(("lateral_offset_x", 12.0, 1.0, 35e6, 40.0, offset_mm))

    rows = []
    for parameter, radius_mm, thickness_mm, conductivity, depth_mm, offset_mm in cases:
        disk = ConductiveDisk(
            radius_m=radius_mm/1000.0,
            thickness_m=thickness_mm/1000.0,
            conductivity_s_m=conductivity,
            depth_m=depth_mm/1000.0,
            x_offset_m=offset_mm/1000.0,
            y_offset_m=0.0,
            rings=6,
        )
        row = {
            "swept_parameter": parameter,
            "radius_mm": radius_mm,
            "thickness_mm": thickness_mm,
            "conductivity_S_m": f"{conductivity:.8g}",
            "depth_mm": f"{depth_mm:.8g}",
            "x_offset_mm": f"{offset_mm:.8g}",
            "rings": 6,
            "ring_segments": 96,
            "receive_peak_v": "",
            "inductance_matrix_condition_inf": "",
            "status": "not_run",
            "error": "",
            "fixture_only": "true",
        }
        try:
            matrix, _, _ = build_disk_model(coil, disk, ring_segments=96)
            peak = receive_peak(simulate(coil, disk, pulse, ring_segments=96))
            row["receive_peak_v"] = f"{peak:.12e}"
            row["inductance_matrix_condition_inf"] = f"{condition_inf(matrix):.8g}"
            row["status"] = "ok"
        except (ValueError, ArithmeticError, OverflowError) as exc:
            row["status"] = "rejected_by_model"
            row["error"] = str(exc)
        rows.append(row)
        print(row)

    output = Path("disk_surrogate_parameter_sweep.csv")
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
