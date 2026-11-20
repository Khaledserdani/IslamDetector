# Finite-cell implementation status

This note records the first executable finite-cell assembly primitives. It is
not a complete disk solver and must not be used to make hardware decisions.

## Implemented

- Rectangular meridional cells with uniform-current basis
  `J_phi = I_i / A_i`.
- Four-dimensional tensor Gauss-Legendre integration for the inductance
  between strictly separated cells, after analytical azimuthal integration.
- A quadrature-order refinement helper that reports convergence or fails
  explicitly.
- Exact diagonal Joule-loss resistance for disjoint piecewise-constant cells,
  retaining the cylindrical volume factor `2*pi*r`.

## Deliberate exclusions

- Self-cell inductance is not implemented.
- Touching and overlapping cell pairs are rejected. Adjacent-cell and
  self-cell integrals need dedicated singularity-aware treatment (for example,
  a derived Duffy/subtraction method) before a complete L matrix can be built.
- This is not yet a matrix assembler for a complete disk mesh, nor is it
  connected to the transient response model.
- The quadrature helper's convergence is an internal numerical check, not an
  independent physical validation.

## Next acceptance gates

1. Derive and implement the self-cell and adjacent-cell weak-singularity
   integration, with no arbitrary distance epsilon.
2. Test the singular integrals against an independently implemented
   reference and refine both cell mesh and quadrature independently.
3. Assemble complete symmetric L and R matrices and test magnetic-energy
   positivity/passivity over multiple meshes.
4. Only then couple the matrices to a transient target-response model.
