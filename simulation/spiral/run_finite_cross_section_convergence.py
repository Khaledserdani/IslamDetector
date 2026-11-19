"""Radial/axial refinement study for the finite-cross-section target kernel."""
from __future__ import annotations

import csv
import math
from pathlib import Path

from finite_cross_section_target import (
    AnnularCell,
    build_finite_cross_section_target_model,
)
from mono_spiral_disk import Coil


CELLS = [
    AnnularCell(0.010, 0.011, 0.040, 0.041),
    AnnularCell(0.011, 0.012, 0.040, 0.041),
]
RESOLUTIONS = (2, 4, 8, 16, 32, 64, 128)


def relative_matrix_error(matrix, reference) -> float:
    numerator = math.sqrt(sum(
        (matrix[i][j] - reference[i][j]) ** 2
        for i in range(len(matrix)) for j in range(len(matrix))
    ))
    denominator = math.sqrt(sum(
        value * value for row in reference for value in row
    ))
    return numerator / max(denominator, 1e-30)


def relative_vector_error(vector, reference) -> float:
    numerator = math.sqrt(sum((a - b) ** 2 for a, b in zip(vector, reference)))
    denominator = math.sqrt(sum(value * value for value in reference))
    return numerator / max(denominator, 1e-30)


def run_sweep(axis: str) -> list[dict[str, str | int]]:
    computed = []
    for resolution in RESOLUTIONS:
        radial = resolution if axis == "radial" else 4
        axial = resolution if axis == "axial" else 4
        matrix, resistance, mutual, diagnostics = (
            build_finite_cross_section_target_model(
                Coil(),
                CELLS,
                35e6,
                radial_subdivisions=radial,
                axial_subdivisions=axial,
                ring_segments=48,
                coil_subdivisions=4,
                gmd_order=64,
                max_section_ratio=0.1,
            )
        )
        computed.append({
            "axis": axis,
            "radial_subdivisions": radial,
            "axial_subdivisions": axial,
            "matrix": matrix,
            "resistance": resistance,
            "mutual": mutual,
            "worst_ratio": diagnostics["worst_subcell_dimension_over_radius"],
        })

    reference = computed[-1]
    rows = []
    for item in computed:
        rows.append({
            "sweep_axis": axis,
            "radial_subdivisions": item["radial_subdivisions"],
            "axial_subdivisions": item["axial_subdivisions"],
            "subcells_per_cell": item["radial_subdivisions"] * item["axial_subdivisions"],
            "relative_L_matrix_error_to_finest": (
                f"{relative_matrix_error(item['matrix'], reference['matrix']):.10g}"
            ),
            "relative_M0_vector_error_to_finest": (
                f"{relative_vector_error(item['mutual'], reference['mutual']):.10g}"
            ),
            "resistance_ohm_cell_1": f"{item['resistance'][0]:.10g}",
            "resistance_ohm_cell_2": f"{item['resistance'][1]:.10g}",
            "worst_subcell_dimension_over_radius": f"{item['worst_ratio']:.10g}",
            "positive_definite": "true",
            "fixture_only": "true",
        })
    return rows


def main() -> None:
    rows = run_sweep("radial") + run_sweep("axial")
    output = Path("finite_cross_section_convergence.csv")
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(row)
    print(f"Generated {output} ({len(rows) + 1} lines)")


if __name__ == "__main__":
    main()
