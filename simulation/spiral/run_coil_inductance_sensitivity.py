"""Sensitivity of the disk surrogate to the provisional coil inductance.

The three values are derived from two published planar-spiral approximations
and their midpoint. They are numerical inputs, not measured coil properties.
"""
from __future__ import annotations

import csv
from pathlib import Path

from mono_spiral_geometry import MonoSpiral
from mono_spiral_disk import (
    Coil, ConductiveDisk, Pulse, build_disk_model, receive_peak, simulate,
)
from run_disk_convergence import matrix_condition_inf


def main() -> None:
    geometry = MonoSpiral()
    current_sheet_h = geometry.mohan_current_sheet_inductance_h
    modified_wheeler_h = geometry.mohan_modified_wheeler_inductance_h
    cases = (
        ("modified_wheeler", modified_wheeler_h),
        ("midpoint_of_estimates", 0.5 * (modified_wheeler_h + current_sheet_h)),
        ("current_sheet", current_sheet_h),
    )

    disk = ConductiveDisk(
        radius_m=0.012,
        thickness_m=0.001,
        conductivity_s_m=35e6,
        depth_m=0.04,
        rings=6,
    )
    pulse = Pulse(time_step_s=0.5e-6)
    rows = []
    for method, inductance_h in cases:
        coil = Coil(inductance_h=inductance_h)
        matrix, _, _ = build_disk_model(coil, disk, ring_segments=96)
        trace = simulate(coil, disk, pulse, ring_segments=96)
        receive_start_s = next(
            row["time_s"] for row in trace if row["phase"] == 2.0
        )
        rows.append({
            "inductance_method": method,
            "coil_inductance_uH": f"{inductance_h * 1e6:.6f}",
            "receive_peak_v": f"{receive_peak(trace):.12e}",
            "peak_primary_current_a": f"{max(abs(row['coil_current_a']) for row in trace):.9g}",
            "receive_phase_start_us": f"{receive_start_s * 1e6:.6f}",
            "inductance_matrix_condition_inf": f"{matrix_condition_inf(matrix):.8g}",
            "fixture_only": "true",
        })
        print(rows[-1])

    output = Path("disk_surrogate_coil_inductance_sensitivity.csv")
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
