# Finite-cell implementation status

This note records the first executable finite-cell assembly primitives. It is
not a complete disk solver and must not be used to make hardware decisions.

## Implemented

- Rectangular meridional cells with uniform-current basis
  `J_phi = I_i / A_i`.
- Four-dimensional tensor Gauss-Legendre integration for the inductance
  between strictly separated cells, after analytical azimuthal integration.
- A quadrature-order refinement helper for separated-cell mutual inductance.
- A dedicated self-cell integral using polar difference coordinates
  `(u,v)=(rho*cos(theta), rho*sin(theta))`; the polar Jacobian `rho`
  regularizes the integrable logarithmic singularity without a distance
  epsilon. A separate order-refinement helper reports convergence or fails.
- Exact diagonal Joule-loss resistance for disjoint piecewise-constant cell
  bases, retaining the cylindrical volume factor `2*pi*r`.
- The angular elliptic kernel computes the complementary elliptic parameter
  directly from squared coordinate differences. This avoids losing the small
  parameter when the usual elliptic parameter rounds to exactly one in
  binary64 near coincident, but distinct, meridional points.

## Deliberate exclusions

- Touching and overlapping *distinct* cell pairs are still rejected.
  Adjacent-cell integrals need a separate singularity-aware treatment before
  a complete L matrix can be built.
- The polar self-cell transform is implemented but not independently validated
  against a separate analytical or 3-D reference. Its order-convergence test
  is a numerical consistency check, not proof of physical correctness.
- This is not yet a matrix assembler for a complete disk mesh, nor is it
  connected to the transient response model.
- The quadrature helper's convergence is an internal numerical check, not an
  independent physical validation.
- The near-coincident angular-kernel regression tests establish finite,
  monotonic behaviour for selected binary64 inputs; they do not constitute an
  independent validation of the complete finite-cell integral.

## Next acceptance gates

1. Independently validate the angular kernel against direct angular
   quadrature, including near-coincident points.
2. Independently validate the polar self-cell integral, then implement
   singularity-aware adjacent-cell integration with no arbitrary distance epsilon.
3. Test singular integrals against an independently implemented reference and
   refine both cell mesh and quadrature independently.
4. Assemble complete symmetric L and R matrices and test magnetic-energy
   positivity/passivity over multiple meshes.
5. Only then couple the matrices to a transient target-response model.

