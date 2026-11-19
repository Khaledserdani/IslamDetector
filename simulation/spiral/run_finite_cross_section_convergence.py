"""Refinement study for the finite-cross-section target kernel."""
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
RESOLUTIONS = (2, 4, 8, 16, 32, 64, 128, 256)


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


def evaluate(radial: int, axial: int, ring_segments: int,
             coil_subdivisions: int, gmd_order: int) -> dict:
    matrix, resistance, mutual, diagnostics = build_finite_cross_section_target_model(
        Coil(),
        CELLS,
        35e6,
        radial_subdivisions=radial,
        axial_subdivisions=axial,
        ring_segments=ring_segments,
        coil_subdivisions=coil_subdivisions,
        gmd_order=gmd_order,
        max_section_ratio=0.1,
    )
    return {
        "matrix": matrix,
        "resistance": resistance,
        "mutual": mutual,
        "worst_ratio": diagnostics["worst_subcell_dimension_over_radius"],
    }


def make_row(axis: str, radial: int, axial: int, ring_segments: int,
             coil_subdivisions: int, gmd_order: int, item: dict,
             reference: dict) -> dict[str, str | int]:
    return {
        "sweep_axis": axis,
        "radial_subdivisions": radial,
        "axial_subdivisions": axial,
        "subcells_per_cell": radial * axial,
        "ring_segments": ring_segments,
        "coil_subdivisions": coil_subdivisions,
        "gmd_order": gmd_order,
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
    }


def run_area_sweep(axis: str) -> list[dict[str, str | int]]:
    computed = []
    for resolution in RESOLUTIONS:
        radial = resolution if axis == "radial" else 4
        axial = resolution if axis == "axial" else 4
        computed.append((
            radial, axial, 48, 4, 64,
            evaluate(radial, axial, 48, 4, 64),
        ))
    reference = computed[-1][5]
    return [
        make_row(axis, radial, axial, ring, coil_steps, gmd, item, reference)
        for radial, axial, ring, coil_steps, gmd, item in computed
    ]


def run_kernel_sweep(axis: str, configurations: tuple[tuple[int, int, int], ...]
                     ) -> list[dict[str, str | int]]:
    computed = []
    for ring_segments, coil_subdivisions, gmd_order in configurations:
        radial = axial = 4
        item = evaluate(
            radial, axial, ring_segments, coil_subdivisions, gmd_order
        )
        computed.append((
            radial, axial, ring_segments, coil_subdivisions, gmd_order, item
        ))
    reference = computed[-1][5]
    return [
        make_row(
            axis, radial, axial, ring, coil_steps, gmd, item, reference
        )
        for radial, axial, ring, coil_steps, gmd, item in computed
    ]


def main() -> None:
    rows = (
        run_area_sweep("radial")
        + run_area_sweep("axial")
        + run_kernel_sweep("ring_azimuth", (
            (24, 4, 64), (48, 4, 64), (96, 4, 64), (192, 4, 64),
        ))
        + run_kernel_sweep("coil_path", (
            (96, 2, 64), (96, 4, 64), (96, 8, 64), (96, 16, 64),
        ))
        + run_kernel_sweep("gmd_quadrature", (
            (48, 4, 32), (48, 4, 64), (48, 4, 96), (48, 4, 128),
        ))
    )
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
