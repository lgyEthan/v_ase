# Cell-Aware Rotation And Commensurate Angle Guide

v_ase separates two operations that look similar in a viewport but have
different periodic meanings:

1. `R` rotates the selected atomic coordinates around the configured pivot.
2. `Cell Transform` constructs a new periodic cell with an integer matrix and
   ASE `make_supercell`.

The selected-coordinate operation supports Selection COM, the last selected
active atom, the global origin, the unit-cell center, or an explicit vector
through the semantic API. An active atom remains unchanged because its
coordinate is the rotation pivot.

The commensurate guide connects these operations. During an axis-locked `R`, it
searches integer combinations of the current 2D periodic cell boundaries,
shows low-strain angular matches in the viewport, and can magnetically snap the
coordinate rotation to a candidate. It does not reject arbitrary angles and it
does not infer strain from bonds.

## Screen-Space Rotation Direction

For selected position `r_i`, pivot `p`, unit axis `k`, and angle `theta`, the
preview remains a rigid Rodrigues rotation:

```text
r_i' = p + R(k, theta) (r_i - p)
```

For `R X`, `R Y`, or `R Z`, `k` is the selected global axis. For free `R`, `k`
points from the scene toward the viewer. Three.js `camera.getWorldDirection()`
points in the opposite direction, so v_ase explicitly negates that convention.
Consequently, a clockwise mouse path produces the same visible clockwise atom
motion in free `R` and in an equivalent axis-locked top view.

## Integer Cell-Boundary Match

Let `A` contain the two current periodic cell vectors after projection onto the
plane perpendicular to the locked rotation axis. ASE uses row-vector cells, so
`A` is a 2 x 2 row matrix. Two integer matrices define candidate supercell
boundaries:

```text
S = M A
T = N A
```

This follows the CellMatch principle of searching combinations of unit-cell
vectors and ranking common cells by the strain needed to fit one boundary to
the other. v_ase removes the best rigid rotation first by solving the 2D
orthogonal Procrustes problem:

```text
Q* = argmin(Q in SO(2)) ||S Q - T||_F
```

For an entered rotation `Q(theta)`, the rotating and reference boundaries are

```text
H_rot = M A Q(theta)
H_ref = N A
```

The remaining boundary deformation is

```text
D = H_rot^-1 H_ref
```

and the displayed mismatch is the largest absolute principal stretch:

```text
epsilon_boundary = max_i |sigma_i(D) - 1|
```

where `sigma_i` are the singular values of `F`. This metric measures the strain
required at the newly matched periodic boundary. It is independent of the
current bond list, bond cutoff, and atom count. The `Boundary strain / %`
control filters candidates by `epsilon_boundary`.

Every retained candidate already satisfies that cutoff. Within one angular
match, v_ase ranks by integer area first and residual strain second, so the
proposed cell is the smallest admissible physical common cell rather than a
larger zero-strain alternative.

For general oblique cells, v_ase performs a bounded search over 2D Hermite
normal-form integer supercells, Gauss-reduces their boundaries, and compares
cells with equal area. For hexagonal and square cells it also uses analytic
commensurate families, which reaches useful small angles without enumerating
millions of generic supercells.

## Hexagonal Series And TBG Reference

For equal-length vectors separated by 60 degrees, the standard commensurate
hexagonal family is

```text
cos(theta_mn) = (m^2 + 4mn + n^2) / (2(m^2 + mn + n^2))
N = m^2 + mn + n^2
```

`N` is the primitive-cell area multiplier. The compact `n = m + 1` series
contains, among others:

```text
(m, n) = (1, 2)   theta = 21.786789 deg   N = 7
(m, n) = (2, 3)   theta = 13.173551 deg   N = 19
(m, n) = (31, 32) theta =  1.050121 deg   N = 2977
```

The last value is a common commensurate approximant near the first twisted
bilayer graphene magic-angle regime. v_ase marks it as `TBG ref` only for an
all-carbon hexagonal structure. It is a geometric reference, not a prediction
of an electronic-energy minimum: the electronic magic angle depends on
interlayer tunneling, relaxation, Fermi velocity, and the chosen Hamiltonian.

## Viewport Guide And Magnetic Snap

`Commensurate guide` is disabled by default. Enable it, start `R`, then lock
`X`, `Y`, or `Z`.

- Thin teal rays leave the active pivot in candidate directions.
- A fixed `CELL MATCHES` strip lists candidate angles without camera-dependent
  label collisions.
- The current magnetic match is amber and its ray is prefixed with `SNAP`.
- The Structure panel reports the active candidate's boundary strain and area
  multiplier `N`.
- The unchanged `0 deg` identity is included, so enabling snap never rotates a
  structure before the pointer or numeric angle actually moves away from zero.
- `Magnetic angle snap` independently enables or disables attraction.
- Magnetic snapping is disabled by default, so the guide never changes a
  rotation unless the user explicitly enables snapping.
- `Snap range / deg` controls the angular capture distance.
- `Max lattice index` controls the analytic search depth; the default `32`
  includes the `1.050121 deg` hexagonal candidate.
- `Max area ratio` limits automatic common-cell proposals. Its default is
  `16`; a larger candidate remains available as an angle guide but is not
  expanded into an impractically large viewport structure.

Turning magnetic snap off leaves every angle continuously editable while
keeping the scientific guide visible. Unlike the removed bond-strain guard, no
rotation is colored invalid or blocked at commit.

The analytic hexagonal candidates are identical for graphene and an ideal
hexagonal h-BN primitive cell because the angle family depends on lattice
geometry, not chemical species. Browser and Python regression tests verify the
`21.786789`, `13.173551`, and `1.050121` degree candidates for both lattices
with zero boundary strain.

## Proposed Common Cell And Boundary Shell

When a committed rotation exactly matches an admissible candidate, v_ase
constructs a separate common-cell proposal. It is not the ordinary
`Replicate cell` display setting.

Let `P_M` and `P_N` be the 3 x 3 row-vector matrices obtained by embedding
`M` and `N` into the two periodic axes. The reference component uses `P_N H`.
The rotating component uses `P_M H`, receives the committed rigid rotation,
and then the residual deformation `D` needed to close the common boundary.
Both components therefore share

```text
H_common = P_N H
```

The proposed-cell atoms are opaque. For inspection only, v_ase also enumerates
one primitive-cell layer outside every 2D boundary. That muted shell is not
part of `H_common`; it exists so bonds crossing the proposed periodic boundary
are visible instead of ending at the cell line. Bond inference uses the same
active element/label cutoffs as the base structure and includes only pairs
with at least one endpoint in the opaque core.

The proposal panel reports the integer matrices, area ratio, boundary strain,
cell lengths/angle, and symmetry-reduced crystallographic notation such as
`(sqrt(7) x sqrt(7)) R19.11 deg`. The renderer preserves the current viewing
direction, frames the complete core and shell, and restores the previous
camera if the proposal is dismissed.

**Set Suggested Cell as Unit Cell** materializes the validated common cell as
an ASE `Atoms` object. Fixed atom and supported directional constraints are
replicated. Cross-layer Hookean constraints and point/plane Hookean anchors are
rejected rather than guessed. Materialization is currently restricted to one
structure without volumetric grids: a trajectory requires a declared
frame-to-frame layer mapping, and a volumetric field requires a declared
layer-specific affine transform. The preview remains available when those
conditions prevent materialization.

## General Integer Cell Transform

The exact reproducible cell operation remains

```text
H' = P H
```

through `ase.build.make_supercell`, where `H` is ASE's 3 x 3 row-vector cell and
`P` is an integer matrix. For a 2D system with non-periodic Z:

```text
P = [[m, n, 0],
     [p, q, 0],
     [0, 0, 1]]
```

v_ase prevents a `Cell Transform` matrix from mixing or repeating a
non-periodic axis. This manual operation applies one matrix to the entire
structure; the commensurate proposal instead uses a validated pair `(M, N)`
for two components and only becomes the unit cell after explicit confirmation.

## References

- P. Lazic, ["CellMatch: Combining two unit cells into a common supercell with minimal strain"](https://doi.org/10.1016/j.cpc.2015.08.038), Computer Physics Communications 197, 324-334 (2015).
- D. S. Koda et al., ["Coincidence Lattices of 2D Crystals: Heterostructure Predictions and Applications"](https://doi.org/10.1021/acs.jpcc.6b01496), Journal of Physical Chemistry C 120, 10895-10908 (2016).
- J. M. B. Lopes dos Santos, N. M. R. Peres, and A. H. Castro Neto, ["Continuum model of the twisted graphene bilayer"](https://doi.org/10.1103/PhysRevB.86.155449), Physical Review B 86, 155449 (2012).
- R. Bistritzer and A. H. MacDonald, ["Moiré bands in twisted double-layer graphene"](https://doi.org/10.1073/pnas.1108174108), PNAS 108, 12233-12237 (2011).
- J. S. Dai, ["An historical review of the theoretical development of rigid body displacements from Rodrigues parameters to the finite twist"](https://doi.org/10.1016/j.mechmachtheory.2005.04.004), Mechanism and Machine Theory 41, 41-52 (2006).
