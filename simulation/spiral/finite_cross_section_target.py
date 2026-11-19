"""Finite-cross-section inductance matrix for axisymmetric annular target cells.

This is an experimental reduced-order kernel, not a validated 3-D eddy-current
solver. Each annular r-z rectangle is represented by a uniform distribution
of coaxial filament loops. Distinct subcells use the AGM elliptic-integral
mutual kernel; each subcell's diagonal uses a rectangular-section GMD self
approximation. The latter is accepted only when its largest section dimension
is small relative to its mean radius. No diagonal regularization is applied.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from mono_spiral_disk import MU0, _coaxial_loop_mutual
from rectangular_cross_section_gmd import rectangular_cross_section_gmd


@dataclass(frozen=True)
class AnnularCell:
    """A rectangular cell in (radius, axial-position), dimensions in metres."""
    r_inner_m: float
    r_outer_m: float
    z_lower_m: float
    z_upper_m: float

    def validate(self) -> None:
        values = (self.r_inner_m, self.r_outer_m, self.z_lower_m, self.z_upper_m)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("cell bounds must be finite")
        if self.r_inner_m <= 0.0 or self.r_outer_m <= self.r_inner_m:
            raise ValueError("cell radii must satisfy 0 < inner < outer")
        if self.z_upper_m <= self.z_lower_m:
            raise ValueError("cell axial bounds must satisfy lower < upper")


@dataclass(frozen=True)
class _Subcell:
    radius_m: float
    z_m: float
    radial_width_m: float
    axial_width_m: float
    area_m2: float


def _subdivide(cell: AnnularCell, radial_subdivisions: int,
               axial_subdivisions: int) -> list[_Subcell]:
    dr = (cell.r_outer_m - cell.r_inner_m) / radial_subdivisions
    dz = (cell.z_upper_m - cell.z_lower_m) / axial_subdivisions
    area = dr * dz
    return [
        _Subcell(
            radius_m=cell.r_inner_m + (i + 0.5) * dr,
            z_m=cell.z_lower_m + (j + 0.5) * dz,
            radial_width_m=dr,
            axial_width_m=dz,
            area_m2=area,
        )
        for i in range(radial_subdivisions)
        for j in range(axial_subdivisions)
    ]


def _self_inductance_gmd(subcell: _Subcell, *, gmd_order: int,
                         max_section_ratio: float) -> float:
    section_ratio = max(
        subcell.radial_width_m, subcell.axial_width_m
    ) / subcell.radius_m
    if section_ratio > max_section_ratio:
        raise ValueError(
            "subcell is too wide for the thin-loop GMD self approximation "
            f"(section/radius={section_ratio:.6g}, "
            f"limit={max_section_ratio:.6g}); refine the cross-section"
        )
    gmd = rectangular_cross_section_gmd(
        subcell.radial_width_m, subcell.axial_width_m, order=gmd_order
    )
    value = MU0 * subcell.radius_m * (
        math.log(8.0 * subcell.radius_m / gmd) - 2.0
    )
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("GMD self-inductance approximation is non-positive")
    return value


def _assert_positive_definite(matrix: list[list[float]]) -> None:
    """Fail closed on a non-positive Cholesky pivot; never regularize."""
    n = len(matrix)
    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            value = matrix[i][j] - sum(
                lower[i][k] * lower[j][k] for k in range(j)
            )
            if i == j:
                if not math.isfinite(value) or value <= 0.0:
                    raise ValueError(
                        "finite-section inductance matrix is not positive "
                        f"definite at pivot {i} (Schur complement {value:.6e} H)"
                    )
                lower[i][j] = math.sqrt(value)
            else:
                lower[i][j] = value / lower[j][j]


def build_finite_cross_section_matrix(
    cells: list[AnnularCell],
    *,
    radial_subdivisions: int = 4,
    axial_subdivisions: int = 4,
    gmd_order: int = 96,
    max_section_ratio: float = 0.1,
) -> tuple[list[list[float]], dict[str, float | int]]:
    """Average loop interactions over finite r-z cells.

    The uniform-area average is evaluated by midpoint subdivision. The
    returned diagnostics expose the actual resolution and the worst local
    section/radius ratio. The 0.1 default is a conservative numerical
    screening setting for the local self approximation, not a universal
    physical validity boundary.
    """
    if not cells:
        raise ValueError("at least one annular cell is required")
    if radial_subdivisions < 1 or axial_subdivisions < 1:
        raise ValueError("subdivision counts must be positive integers")
    if gmd_order < 8 or gmd_order > 512:
        raise ValueError("gmd_order must be between 8 and 512")
    if not math.isfinite(max_section_ratio) or max_section_ratio <= 0.0:
        raise ValueError("max_section_ratio must be finite and positive")
    for cell in cells:
        cell.validate()

    # Overlapping volume cells would double-count current-carrying material.
    for i, first in enumerate(cells):
        for second in cells[i + 1:]:
            radial_overlap = min(first.r_outer_m, second.r_outer_m) - max(
                first.r_inner_m, second.r_inner_m
            )
            axial_overlap = min(first.z_upper_m, second.z_upper_m) - max(
                first.z_lower_m, second.z_lower_m
            )
            if radial_overlap > 0.0 and axial_overlap > 0.0:
                raise ValueError("annular cells must not overlap in r-z volume")

    samples = [
        _subdivide(cell, radial_subdivisions, axial_subdivisions)
        for cell in cells
    ]
    all_samples = [sample for group in samples for sample in group]
    worst_ratio = max(
        max(sample.radial_width_m, sample.axial_width_m) / sample.radius_m
        for sample in all_samples
    )
    self_values = [
        [
            _self_inductance_gmd(
                sample, gmd_order=gmd_order,
                max_section_ratio=max_section_ratio,
            )
            for sample in group
        ]
        for group in samples
    ]

    count = len(cells)
    matrix = [[0.0] * count for _ in range(count)]
    for i in range(count):
        for j in range(i, count):
            total = 0.0
            for p, first in enumerate(samples[i]):
                for q, second in enumerate(samples[j]):
                    if i == j and p == q:
                        mutual = self_values[i][p]
                    else:
                        mutual = _coaxial_loop_mutual(
                            first.radius_m, second.radius_m,
                            abs(first.z_m - second.z_m),
                        )
                    total += mutual
            average = total / (len(samples[i]) * len(samples[j]))
            matrix[i][j] = matrix[j][i] = average

    _assert_positive_definite(matrix)
    return matrix, {
        "cell_count": count,
        "radial_subdivisions": radial_subdivisions,
        "axial_subdivisions": axial_subdivisions,
        "subcells_per_cell": radial_subdivisions * axial_subdivisions,
        "worst_subcell_dimension_over_radius": worst_ratio,
    }
