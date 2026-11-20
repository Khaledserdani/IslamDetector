"""Finite meridional-cell assembly primitives for axisymmetric disk models.

Only mutually separated rectangular cells are integrated for L at this stage.
Self-cell and touching/near-singular pairs are deliberately rejected pending a
dedicated singularity-aware quadrature. No diagonal epsilon or centroid
filament approximation is used.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from axisymmetric_disk_kernel import (
    MU0,
    finite_cell_inductance_integrand_h_per_m4,
)


@dataclass(frozen=True)
class MeridionalCell:
    """Rectangular cell in (r,z), with uniform J_phi = I / area."""
    r0_m: float
    r1_m: float
    z0_m: float
    z1_m: float

    def __post_init__(self) -> None:
        values = (self.r0_m, self.r1_m, self.z0_m, self.z1_m)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("cell bounds must be finite")
        if self.r0_m < 0.0 or self.r1_m <= self.r0_m:
            raise ValueError("cell radial bounds must satisfy 0 <= r0 < r1")
        if self.z1_m <= self.z0_m:
            raise ValueError("cell axial bounds must satisfy z0 < z1")

    @property
    def area_m2(self) -> float:
        return (self.r1_m - self.r0_m) * (self.z1_m - self.z0_m)


def _gauss_legendre(order: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Compute Gauss-Legendre nodes and weights on [-1, 1]."""
    if order < 2:
        raise ValueError("quadrature order must be at least 2")
    nodes = [0.0] * order
    weights = [0.0] * order
    half = (order + 1) // 2
    for i in range(half):
        x = math.cos(math.pi * (i + 0.75) / (order + 0.5))
        for _ in range(100):
            p0, p1 = 1.0, x
            for degree in range(2, order + 1):
                p0, p1 = p1, ((2 * degree - 1) * x * p1 - (degree - 1) * p0) / degree
            derivative = order * (x * p1 - p0) / (x * x - 1.0)
            step = p1 / derivative
            x -= step
            if abs(step) < 2.0e-15:
                break
        else:
            raise ArithmeticError("Gauss-Legendre root iteration did not converge")
        p0, p1 = 1.0, x
        for degree in range(2, order + 1):
            p0, p1 = p1, ((2 * degree - 1) * x * p1 - (degree - 1) * p0) / degree
        derivative = order * (x * p1 - p0) / (x * x - 1.0)
        weight = 2.0 / ((1.0 - x * x) * derivative * derivative)
        nodes[i], nodes[order - 1 - i] = -x, x
        weights[i] = weights[order - 1 - i] = weight
    return tuple(nodes), tuple(weights)


def _interval_rule(lo: float, hi: float, nodes: tuple[float, ...],
                   weights: tuple[float, ...]) -> tuple[tuple[float, float], ...]:
    mid = 0.5 * (lo + hi)
    half = 0.5 * (hi - lo)
    return tuple((mid + half * x, half * w) for x, w in zip(nodes, weights))


def _meridional_gap(a: MeridionalCell, b: MeridionalCell) -> float:
    dr = max(a.r0_m - b.r1_m, b.r0_m - a.r1_m, 0.0)
    dz = max(a.z0_m - b.z1_m, b.z0_m - a.z1_m, 0.0)
    return math.hypot(dr, dz)


def mutual_inductance_h(
    cell_a: MeridionalCell,
    cell_b: MeridionalCell,
    order: int = 6,
) -> float:
    """Integrate L_ab over two strictly separated rectangular cells [H].

    Four-dimensional tensor Gauss-Legendre quadrature is used after exact
    azimuthal integration. Cells that overlap or touch are rejected because
    this routine is not a self/near-singular quadrature.
    """
    if _meridional_gap(cell_a, cell_b) <= 0.0:
        raise ValueError("overlapping or touching cells require singularity-aware quadrature")
    nodes, weights = _gauss_legendre(order)
    a_r = _interval_rule(cell_a.r0_m, cell_a.r1_m, nodes, weights)
    a_z = _interval_rule(cell_a.z0_m, cell_a.z1_m, nodes, weights)
    b_r = _interval_rule(cell_b.r0_m, cell_b.r1_m, nodes, weights)
    b_z = _interval_rule(cell_b.z0_m, cell_b.z1_m, nodes, weights)
    total = 0.0
    for ra, wra in a_r:
        for za, wza in a_z:
            for rb, wrb in b_r:
                for zb, wzb in b_z:
                    density = finite_cell_inductance_integrand_h_per_m4(
                        ra, za, rb, zb, cell_a.area_m2, cell_b.area_m2
                    )
                    total += wra * wza * wrb * wzb * density
    return total


def converged_mutual_inductance_h(
    cell_a: MeridionalCell,
    cell_b: MeridionalCell,
    orders: tuple[int, ...] = (4, 6, 8, 10, 12),
    relative_tolerance: float = 1.0e-6,
) -> tuple[float, int]:
    """Return last converged L_ab and quadrature order, or raise."""
    if not math.isfinite(relative_tolerance) or relative_tolerance <= 0.0:
        raise ValueError("relative_tolerance must be finite and positive")
    previous = None
    for order in orders:
        current = mutual_inductance_h(cell_a, cell_b, order)
        if previous is not None:
            scale = max(abs(current), abs(previous), 1.0e-30)
            if abs(current - previous) <= relative_tolerance * scale:
                return current, order
        previous = current
    raise ArithmeticError("mutual inductance quadrature did not converge")


def resistance_matrix_ohm(
    cells: tuple[MeridionalCell, ...],
    conductivity_s_per_m: float,
) -> tuple[tuple[float, ...], ...]:
    """Return exact Joule-loss R for disjoint piecewise-constant cell bases.

    R_ii = (1/sigma) * integral_cell (1/A_i^2) dV, with
    dV = 2*pi*r dr dz. Off-diagonal entries vanish for disjoint supports.
    """
    if not math.isfinite(conductivity_s_per_m) or conductivity_s_per_m <= 0.0:
        raise ValueError("conductivity must be finite and positive")
    result = []
    for i, cell in enumerate(cells):
        for other in cells[:i]:
            radial_overlap = min(cell.r1_m, other.r1_m) - max(cell.r0_m, other.r0_m)
            axial_overlap = min(cell.z1_m, other.z1_m) - max(cell.z0_m, other.z0_m)
            if radial_overlap > 0.0 and axial_overlap > 0.0:
                raise ValueError("resistance basis requires non-overlapping cell interiors")
        radial_integral = 0.5 * (cell.r1_m**2 - cell.r0_m**2)
        volume = 2.0 * math.pi * radial_integral * (cell.z1_m - cell.z0_m)
        diagonal = volume / (conductivity_s_per_m * cell.area_m2**2)
        row = [0.0] * len(cells)
        row[i] = diagonal
        result.append(tuple(row))
    return tuple(result)


def self_inductance_h(
    cell: MeridionalCell,
    order: int = 6,
) -> float:
    """Integrate one rectangular cell's self-inductance using difference polar coordinates.

    For source/field meridional coordinates x=(r,z), y=x+(u,v), the
    four-dimensional domain is transformed to (rho,theta,r,z). The polar
    Jacobian rho regularizes the logarithmic angular-kernel singularity at
    u=v=0. Gauss nodes are interior, so the singular point is never sampled.
    This is a dedicated self-cell integral, not an epsilon-regularized kernel.
    """
    nodes, weights = _gauss_legendre(order)
    dr = cell.r1_m - cell.r0_m
    dz = cell.z1_m - cell.z0_m
    total = 0.0
    # The limiting radius changes branch at atan(dz/dr). Split each
    # quadrant there so Gauss-Legendre never spans that derivative kink.
    switch = math.atan2(dz, dr)
    angular_rules = (
        (0.0, switch), (switch, 0.5 * math.pi),
    )
    for theta_lo, theta_hi in angular_rules:
      for theta, wtheta in _interval_rule(theta_lo, theta_hi, nodes, weights):
        ct, st = math.cos(theta), math.sin(theta)
        abs_ct, abs_st = abs(ct), abs(st)
        rho_max = min(dr / abs_ct if abs_ct > 1.0e-14 else math.inf,
                      dz / abs_st if abs_st > 1.0e-14 else math.inf)
        # rho = rho_max*t^2 smooths the rho*log(rho) endpoint behaviour.
        for rho_unit, wrho in zip(nodes, weights):
            t = 0.5 * (rho_unit + 1.0)
            rho = rho_max * t * t
            wr = rho_max * t * wrho
            u, v = rho * ct, rho * st
            r_lo = max(cell.r0_m, cell.r0_m - u)
            r_hi = min(cell.r1_m, cell.r1_m - u)
            z_lo = max(cell.z0_m, cell.z0_m - v)
            z_hi = min(cell.z1_m, cell.z1_m - v)
            if r_hi <= r_lo or z_hi <= z_lo:
                continue
            r_rule = _interval_rule(r_lo, r_hi, nodes, weights)
            z_rule = _interval_rule(z_lo, z_hi, nodes, weights)
            for r, wr_base in r_rule:
                for z, wz_base in z_rule:
                    density = finite_cell_inductance_integrand_h_per_m4(
                        r, z, r + u, z + v,
                        cell.area_m2, cell.area_m2,
                    )
                    total += (
                        4.0 * wtheta * wr * wr_base * wz_base * rho * density
                    )
    return total



def converged_self_inductance_h(
    cell: MeridionalCell,
    orders: tuple[int, ...] = (4, 6, 8, 10),
    relative_tolerance: float = 2.0e-4,
) -> tuple[float, int]:
    """Return self-inductance and quadrature order after successive-order agreement."""
    if not math.isfinite(relative_tolerance) or relative_tolerance <= 0.0:
        raise ValueError("relative_tolerance must be finite and positive")
    previous = None
    for order in orders:
        current = self_inductance_h(cell, order)
        if previous is not None:
            scale = max(abs(current), abs(previous), 1.0e-30)
            if abs(current - previous) <= relative_tolerance * scale:
                return current, order
        previous = current
    raise ArithmeticError("self-cell quadrature did not converge")
