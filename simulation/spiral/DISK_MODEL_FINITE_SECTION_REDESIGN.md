# Finite-section redesign for the conductive-disk surrogate

Status: design note only. This document does not claim that a finite-section solver has been implemented or validated.

## 1. Current model audit

The current `mono_spiral_disk.py` uses equal-area annuli with

- edges \(r_i=R\sqrt{i/N}\),
- representative radii at the midpoint in area,
- a rectangular-section GMD in each annulus self term,
- filament-loop mutual inductance at the representative radii,
- filament Neumann coupling between the spiral and each target ring.

This mixes two different current representations. The self term treats each annulus as a conductor with finite radial width and thickness, while mutual terms treat that same current as a filament at one radius. The approximation is not a single consistent Galerkin/Rayleigh-Ritz discretization. A Cholesky failure is therefore a useful rejection signal, but it does not identify a unique physical cause.

The GMD is only a cross-section logarithmic-distance primitive. It does not, by itself, turn the thin-loop self-inductance expression into an exact finite-annulus self term.

## 2. Replacement unknown: azimuthal current density

For an axisymmetric disk, represent the eddy current as an azimuthal current density \(J_\phi(r,z)\), rather than as a set of thin circular filaments.

Partition the meridional \((r,z)\) cross-section into cells \(S_i\). Use basis functions \(b_i(r,z)\) with a clear normalization, for example

\[
J_\phi(r,z,t)=\sum_i I_i(t)b_i(r,z),\qquad
\int_{S_i}b_i(r,z)\,dr\,dz=1.
\]

For a piecewise-constant cell basis, \(b_i=1/|S_i|\) inside cell \(S_i\) and zero outside. The coordinate \(I_i\) then has units of ampere and is the current crossing a meridional section of that cell. The azimuthal direction makes each basis current divergence-free inside the axisymmetric model.

The innermost cell is an ordinary finite-area cell touching the axis; it is not represented by a loop whose radius is assigned an arbitrary nonzero value.

## 3. Build L and R from the same basis

Construct every inductance entry from the magnetic-energy bilinear form using the same spatial basis for self and mutual terms:

\[
L_{ij}=\frac{\mu_0}{4\pi}
\int_{V_i}\!\int_{V_j}
\frac{b_i(r,z)b_j(r',z')\,
\hat{\boldsymbol\phi}\!\cdot\!\hat{\boldsymbol\phi}'}
{|\mathbf x-\mathbf x'|}
\,dV'\,dV.
\]

Here \(dV= r\,dr\,d\phi\,dz\), and the angular coordinates are integrated over a full revolution. This expression is schematic for the axisymmetric reduction; implementation should use a derived and independently checked elliptic-kernel form or a verified 3-D quadrature. Do not substitute a point-filament kernel at cell centroids for the finite-cell double integral.

For the same basis, derive the resistance matrix from Joule loss:

\[
R_{ij}=\int_V \frac{b_i b_j}{\sigma}\,dV.
\]

For disjoint piecewise-constant cells this is diagonal, with the cylindrical volume weighting retained. This is more consistent than evaluating a ring circumference at one representative radius.

The coil-to-target mutual vector must use the same target basis and the actual continuous spiral path. Check reciprocity by computing the same coupling from both sides.

## 4. Singular and near-singular integration

The kernel is weakly singular when source and field points coincide. Its integral over finite cells is integrable, but naive centroid sampling is not reliable.

Required approach:

1. Derive the axisymmetric angular integral, including its elliptic-integral kernel and limiting behaviour as \((r,z)\to(r',z')\).
2. Integrate the remaining meridional cell-pair integral with adaptive or singularity-aware quadrature.
3. For self cells, use a dedicated self-cell integral or validated analytic subtraction; do not add an arbitrary epsilon to the distance.
4. For adjacent cells, use near-singular quadrature or subdivide until the integral is converged.
5. Keep all length units in SI and document every normalization.

## 5. Acceptance tests before replacing the surrogate

- **Symmetry:** \(L_{ij}=L_{ji}\) within a stated numerical tolerance.
- **Energy:** for arbitrary test current vectors \(I\), verify \(I^TLI\geq 0\) within the integration error budget. Positive semidefinite is the physical energy requirement; do not demand a strictly positive pivot when the basis contains redundant or dependent modes.
- **Reciprocity:** coil-to-cell mutual coupling agrees in both directions.
- **Mesh convergence:** refine radial and thickness partitions independently; report each matrix entry, eigenvalue spectrum, receive waveform, and peak change.
- **Quadrature convergence:** increase integration order/tolerance independently of mesh refinement.
- **Independent reference:** compare coaxial finite-section cases against an independent analytical or separately implemented numerical solution.
- **Limiting cases:** thin-section limits approach the corresponding filament formulas where their assumptions hold; low-conductivity and large-depth limits behave continuously.
- **Passivity:** the coupled RL model must not generate magnetic energy or sustained target current without input.

A single successful Cholesky factorization, a positive diagonal, or a finite receive voltage is not sufficient validation.

## 6. Keep the model honest

The disk is a synthetic axisymmetric target fixture. The reduced model omits non-axisymmetric target shapes, soil response, coil winding cross-section, switching-device dynamics, receiver loading, and real measured target properties. Outputs must remain labelled simulation-only until independently validated against measurements.

## 7. Implementation sequence

1. Add a standalone finite-cell kernel module with unit tests for normalization, symmetry, and limiting cases.
2. Add a finite-cell inductance/resistance assembler without changing the existing surrogate.
3. Compare it against the current ring model on simple coaxial fixtures.
4. Add mesh and quadrature convergence reports.
5. Only after those pass, connect the new matrix to the transient solver and compare waveforms.
6. Retain the current surrogate as a clearly labelled legacy baseline until the replacement is validated.

No hardware purchase decision should be based on the present target model or this design note.
