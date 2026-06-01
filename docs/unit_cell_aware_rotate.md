# Cell-Aware Transform And Rotate Guard

For periodic twist or moire-style work, v_ase treats the true unit-cell-aware operation as an ASE `make_supercell(P)` transform, not as a selected-atom rotate. The `Cell Transform` panel applies a 3 x 3 integer matrix `P` to the full structure and every trajectory frame:

```text
H' = P H
```

where `H` is ASE's row-vector cell matrix:

```text
H = [a
     b
     c]
```

This is the same convention used by `ase.build.make_supercell`: the transformed cell metric is `P h_p = h`.

For 2D periodic systems, keep the non-periodic axis as the identity column, for example:

```text
P = [[m, n, 0],
     [p, q, 0],
     [0, 0, 1]]
```

This creates a commensurate 2D supercell while preserving the out-of-plane direction. If an axis is non-periodic, v_ase requires both the matching row and column of `P` to stay identical to the identity matrix so the vacuum direction is not mixed, tilted, or repeated by accident.

A twisted bilayer workflow should generate or choose the appropriate integer matrices for each layer/supercell first, then use this matrix transform to create editable periodic cells. An angle-only twist control can be built on top of this later, but the reproducible operation is still the integer supercell transform.

The ordinary `R` rotate remains an atom-editing operation. It supports three rotate pivots:

- `Selection COM`: arithmetic center of editable selected atom positions.
- `Global origin`: Cartesian `(0, 0, 0)`.
- `Unit-cell center`: Cartesian `(a + b + c) / 2` for cell vectors `a`, `b`, and `c`.

## Rotation

For selected atom position `r_i`, pivot `p`, unit axis `k`, and angle `theta`, the preview position is

```text
r_i' = p + R(k, theta) (r_i - p)
```

where `R(k, theta)` is the Euler-Rodrigues / Rodrigues finite rotation. In vector form:

```text
R(k, theta) v = v cos(theta) + (k x v) sin(theta) + k (k . v) (1 - cos(theta)).
```

The implementation uses Three.js quaternions, which are numerically equivalent to this axis-angle formula.

## Periodic Minimum Image

For a bonded pair `(i, j)`, the periodic displacement is computed in fractional coordinates:

```text
Delta r_ij = r_j - r_i
Delta s_ij = H^{-1} Delta r_ij
Delta s_ij,alpha <- Delta s_ij,alpha - nint(Delta s_ij,alpha)  if PBC_alpha is true
Delta r_ij^MIC = H Delta s_ij
```

`H = [a b c]` is the cell matrix. The bond length used for validation is

```text
l_ij = ||Delta r_ij^MIC||.
```

This is the minimum image convention used in molecular simulation with periodic boundary conditions.

## Bond-Strain Guard

When `Bond-strain guard` is enabled, v_ase records reference MIC bond lengths before rotate preview:

```text
l_ij^0 = ||Delta r_ij^MIC,0||.
```

During preview it computes per-bond engineering strain:

```text
epsilon_ij = |l_ij' - l_ij^0| / max(l_ij^0, eps).
```

Rotate is blocked if any affected bond exceeds the user cutoff:

```text
max_(i,j in B_affected) epsilon_ij > epsilon_cutoff.
```

Affected bonds are those inferred from the current bond settings where at least one atom is in the selected editable set. Violating bonds are drawn as red guide cylinders and commit is refused until the preview returns below cutoff or the validation is disabled.

The metric is intentionally a local bond-stretch criterion, not a full Green-Lagrange strain tensor. That choice keeps the preview robust when neighbor correspondence is ambiguous and matches the physical interpretation that excessive bond stretching is the first-order reason to reject an interactive rigid rotate in a periodic structure editor.

## References

- U. K. Deiters, "Minimum Image Convention Coding of Microcomputers", Molecular Simulation 3, 343-344 (1989), DOI: 10.1080/08927028908031386.
- D. Xu, T. Thaiyanurak, and N. Salsabil, "Atomic Bond Strain: A New Strain Measure Displaying Nearly Perfect Linear Correlation with Stress Throughout Plastic Deformation of Single-Crystal FCC Metals", Solids 7, 5 (2026), DOI: 10.3390/solids7010005.
- J. S. Dai, "An historical review of the theoretical development of rigid body displacements from Rodrigues parameters to the finite twist", Mechanism and Machine Theory 41, 41-52 (2006), DOI: 10.1016/j.mechmachtheory.2005.04.004.
