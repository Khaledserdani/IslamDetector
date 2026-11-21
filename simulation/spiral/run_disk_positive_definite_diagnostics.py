"""Check whether rejected disk fixtures recover with finer ring polygon quadrature."""
from __future__ import annotations

import csv
from pathlib import Path

from mono_spiral_disk import Coil, ConductiveDisk, build_disk_model
from run_disk_convergence import matrix_condition_inf


def main() -> None:
    cases = (
        ("small_radius", 0.006, 0.001),
        ("thick_disk", 0.012, 0.002),
    )
    resolutions = (48, 96, 128, 192, 256, 384)
    coil = Coil()
    rows = []
    for case_name, radius_m, thickness_m in cases:
        for ring_segments in resolutions:
            disk = ConductiveDisk(
                radius_m=radius_m,
                thickness_m=thickness_m,
                conductivity_s_m=35e6,
                depth_m=0.04,
                rings=6,
            )
            row = {
                "case": case_name,
                "radius_mm": radius_m * 1000.0,
                "thickness_mm": thickness_m * 1000.0,
                "rings": 6,
                "ring_segments": ring_segments,
                "status": "not_run",
                "condition_inf": "",
                "error": "",
                "fixture_only": "true",
            }
            try:
                matrix, _, _ = build_disk_model(
                    coil, disk, ring_segments=ring_segments
                )
                row["condition_inf"] = f"{matrix_condition_inf(matrix):.10g}"
                row["status"] = "positive_definite"
            except (ValueError, ArithmeticError, OverflowError) as exc:
                row["status"] = "rejected"
                row["error"] = str(exc)
            rows.append(row)
            print(row)

    output = Path("disk_positive_definite_resolution_diagnostics.csv")
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {output} ({len(rows) + 1} lines)")


if __name__ == "__main__":
    main()
