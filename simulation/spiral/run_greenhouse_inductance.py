"""Run Greenhouse-style Mono Spiral inductance quadrature convergence."""
from __future__ import annotations

import csv
from pathlib import Path

from greenhouse_inductance import calculate_mono_spiral_inductance


def main() -> None:
    orders = ((2, 8), (4, 16), (8, 32))
    rows = []
    previous = None
    for radial_order, angular_order in orders:
        report = calculate_mono_spiral_inductance(
            radial_order=radial_order,
            angular_order=angular_order,
        )
        relative_change = (
            ""
            if previous is None
            else f"{abs(report.inductance_h - previous) / report.inductance_h:.10e}"
        )
        row = {
            "radial_order": radial_order,
            "angular_order": angular_order,
            "segment_count": report.segment_count,
            "parallel_pair_count": report.parallel_pair_count,
            "perpendicular_pair_count": report.perpendicular_pair_count,
            "path_length_m": f"{report.path_length_m:.10f}",
            "self_sum_uH": f"{report.self_sum_h * 1e6:.9f}",
            "mutual_positive_uH": f"{report.mutual_positive_h * 1e6:.9f}",
            "mutual_negative_uH": f"{report.mutual_negative_h * 1e6:.9f}",
            "inductance_uH": f"{report.inductance_h * 1e6:.9f}",
            "relative_change_from_previous": relative_change,
            "partial_quasistatic_estimate_only": "true",
        }
        rows.append(row)
        print(row)
        previous = report.inductance_h

    if len(rows) >= 2:
        final_change = float(rows[-1]["relative_change_from_previous"])
        if final_change > 1e-3:
            raise ArithmeticError(
                f"cross-section quadrature did not converge to 0.1%: {final_change:.6g}"
            )

    output = Path("greenhouse_inductance_convergence.csv")
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {output} ({len(rows) + 1} lines)")


if __name__ == "__main__":
    main()
