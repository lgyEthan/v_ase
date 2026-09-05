# Commensurate Cell Scientific Validation

This document records the equations, acceptance criterion, reference fixtures,
and performance boundary used by the v_ase commensurate-cell workspace.

```{contents} On this page
:local:
:depth: 1
```

## Scope

The validated workflow matches two periodic vectors in the global XY plane and
rotates the guest about global Z. It supports either:

- a selected component copied from the host cell for a same-lattice twist; or
- a separately loaded host and guest lattice.

It does not claim an energy minimum. The result is a geometrically periodic,
bounded integer-cell match that should be relaxed with an appropriate physical
model before energetic conclusions are drawn.

## Integer Search And Rotation

For host and guest row-vector bases `A_h` and `A_g`, integer matrices define
candidate boundaries

```text
H = M_h A_h
G = M_g A_g.
```

v_ase enumerates inequivalent 2D Hermite-normal-form cells, Gauss-reduces their
bases, and removes the best proper in-plane rotation by an orthogonal
Procrustes solve. The remaining deformation that maps the rotated guest onto
the host is

```text
D_g = (G Q)^-1 H.
```

The implementation checks equivalent determinant-one reduced-basis
orientations. Regression fixtures verify that equivalent unimodular input
bases recover the same physical matches in the tested cases.

This is an adaptation of the cited methods: HNF enumeration, Gauss reduction,
and a finite orientation set replace the paper's integer-entry search and
alignment construction. The graph retains a ranked representative per 0.01°
bucket. The tests establish the listed analytic cases and agreement with
unscreened enumeration of this orientation set; they are not a proof of
completeness over arbitrary deformations or all lattice representations.

Since 0.3.1, plane alignment requires a normal dot product of at least
`1 − 1e-10`. The former `0.985` bound admitted visibly tilted periodic cells,
which could hide out-of-plane deformation in a projected match.

## Two Strain Values

Candidate acceptance uses the conservative, rotation-invariant maximum
principal-stretch mismatch

```text
epsilon_max = max_i |sigma_i(D) - 1|,
```

where `sigma_i` are singular values. The **Maximum strain** control applies to
this value only.

The optional **Paper strain projection** uses the small-strain tensor

```text
epsilon = (D + D^T) / 2 - I
epsilon_mean = (|epsilon_11| + |epsilon_22| + |epsilon_12|) / 3.
```

This is the mean absolute strain plotted against common-cell atom count by
Stradi et al. Keeping both values prevents a change of graph view from changing
which candidates pass the physical cutoff.

The regression suite also reconstructs all six mean-strain values in Table 3
of Stradi et al. from the published `epsilon_11`, `epsilon_22`, and
`epsilon_12` components. The comparison allows one final-table rounding unit
because the printed components are already rounded to two decimal percent.

## Numerical References

### Equal-lattice hexagonal series

For the standard commensurate twisted-bilayer family,

```text
cos(theta_mn) = (m^2 + 4mn + n^2) / (2(m^2 + mn + n^2))
N = m^2 + mn + n^2.
```

The test suite checks every `(m, m + 1)` point through `(31, 32)`, including
`21.786789 deg` (`N=7`), `13.173551 deg` (`N=19`), and `1.050121 deg`
(`N=2977`), with zero residual boundary strain.

### Separate graphene/Cu(111) fixture

The user-facing fixture in
[periodic host/guest workflow](periodic-interfaces.md)
uses separate graphene and ideal Cu(111) primitive cells. Under a one-percent
guest-strain cutoff and area limit 16, its smallest match is:

```text
host:  graphene √13
guest: Cu(111) √12
|rotation|: 16.10211375 deg
maximum principal guest strain: 0.1665824397 %
mean absolute guest strain:     0.1110549598 %
```

`expected.json` is read directly by the regression suite. The fixture validates
lattice matching and visualization; it is not a relaxed interface model.

The default proposal is sorted by the larger host/guest area ratio, then total
area, residual strain, and angle magnitude. Increasing the area ceiling to 64
therefore keeps this `√13/√12` cell as the initial proposal instead of replacing
it with a larger cell closer to zero rotation. Once the user supplies an angle,
the viewport deliberately follows the admissible candidate nearest that angle.

The reference values are also reconstructed independently in the tests:

```text
L_h = √13 * 2.46 Angstrom
L_g = √12 * (3.615 / √2) Angstrom
epsilon_max = L_h / L_g - 1
epsilon_mean = 2 * epsilon_max / 3
theta = 30 deg - atan((√3/2) / 3.5)
```

The expected common cell contains 26 graphene atoms and 12 Cu atoms. The
external guest placement is independently validated using

```text
guest minimum z - host maximum z = 3 Angstrom
```

before the guest rotation and in-plane residual deformation are applied.

## Viewport State Validation

The browser regression verifies the complete user workflow rather than only
the search result:

1. enabling the workspace without a selection shows only the host primitive
   grid and its two vectors;
2. selecting a same-cell layer adds a separately colored guest grid and two
   guest vectors without moving the camera;
3. loading an external guest replaces the selected guest, preserves the 3 Å
   gap, and keeps separate host/guest integer matrices;
4. cells-only is the default; optional atom mode adds an opaque core, a
   one-cell halo, and boundary-crossing bonds;
5. the graph uses rotation angle, area ratio, and maximum principal strain as
   distinct dimensions and moves only the current-angle plane during rotation;
6. materialization requires an explicit Edit-mode action and preserves the
   camera instead of reframing the result.

### Accelerated-versus-complete search

A deterministic general oblique host/guest pair is searched through area
ratio 5 twice: once with the production descriptor-tree/vectorized path and
once by complete host-matrix, guest-matrix, and canonical basis-orientation
enumeration. Candidate angle buckets, area ratios, and strains must be
identical. Separate random-boundary tests compare the closed-form batched
kinematics against SVD solves.

## Performance Boundary

The search uses descriptor-space `cKDTree` screening, vectorized closed-form
2 x 2 rotation/deformation evaluation, and enriches only the best physical
candidate in each 0.01-degree bucket. It does not randomly sample candidates.

On the release development machine, the graphene/hBN-like benchmark evaluates:

| Maximum area ratio | Compared boundary pairs | Search time |
| ---: | ---: | ---: |
| 16 | 1,379 | about 0.016 s |
| 32 | 19,098 | about 0.09 s |
| 64 | 296,075 | about 0.82 s |
| 128 | 4,731,795 | about 9.7 s |

Hardware changes absolute timing. The explicit maximum of 128 keeps the
interactive search bounded; larger-area studies should use a dedicated
offline lattice-matching workflow rather than an implicit incomplete sample.

## References

- P. Lazic, "CellMatch: Combining two unit cells into a common supercell with
  minimal strain," *Computer Physics Communications* 197, 324-334 (2015),
  DOI: [10.1016/j.cpc.2015.08.038](https://doi.org/10.1016/j.cpc.2015.08.038).
- D. Stradi, L. Jelver, S. Smidstrup, and K. Stokbro, "Method for determining
  optimal supercell representation of interfaces," *Journal of Physics:
  Condensed Matter* 29, 185901 (2017), DOI:
  [10.1088/1361-648X/aa66f3](https://doi.org/10.1088/1361-648X/aa66f3).
- J. M. B. Lopes dos Santos, N. M. R. Peres, and A. H. Castro Neto,
  "Continuum model of the twisted graphene bilayer," *Physical Review B* 86,
  155449 (2012), DOI:
  [10.1103/PhysRevB.86.155449](https://doi.org/10.1103/PhysRevB.86.155449).
  Equations 5-7 give the commensurate angle and primitive integer-cell family
  used by the analytic same-lattice regression.
