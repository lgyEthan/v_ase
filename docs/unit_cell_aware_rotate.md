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

The opt-in commensurate workspace connects these operations. It searches
integer combinations of two in-plane periodic boundaries immediately, shows
low-strain angular matches, and can magnetically snap a selected layer or an
independent guest structure to a candidate. It does not infer strain from
bonds. To keep the periodic construction unambiguous, commensurate rotation is
restricted to global Z and the matched lattice vectors must lie in XY.

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

Let `A_h` and `A_g` contain the two host and guest periodic cell vectors after
projection into the shared XY frame. ASE uses row-vector cells, so each is a
2 x 2 row matrix. Integer matrices define candidate supercell boundaries:

```text
H = M_h A_h
G = M_g A_g
```

For same-lattice twist, `A_h = A_g` and the selected atoms are the guest layer.
For independent host/guest matching, the two bases and primitive areas may
differ. This follows the CellMatch principle of searching combinations of
unit-cell vectors and ranking common cells by the strain needed to fit one
boundary to the other. v_ase removes the best rigid rotation first by solving
the 2D orthogonal Procrustes problem:

```text
Q* = argmin(Q in SO(2)) ||G Q - H||_F
```

For an entered rotation `Q(theta)`, the guest and host boundaries are

```text
G_rot = M_g A_g Q(theta)
H_ref = M_h A_h
```

The remaining boundary deformation is

```text
D_g = G_rot^-1 H_ref
```

and the displayed mismatch is the largest absolute principal stretch:

```text
epsilon_guest = max_i |sigma_i(D_g) - 1|
```

where `sigma_i` are the singular values. This is the default guest-strain
construction. If the user explicitly chooses host strain, the common boundary
is the rigidly rotated guest boundary and v_ase instead evaluates
`D_h = H_ref^-1 G_rot`, with

```text
epsilon_host = max_i |sigma_i(D_h) - 1|
```

The active residual is independent of the current bond list, bond cutoff, and
atom count. The `Boundary strain / %` control filters candidates by the
selected target's principal stretch.

For comparison with the interface-search plot of Stradi et al., v_ase also
reports the small-strain tensor and its mean absolute component value:

```text
epsilon = (D + D^T) / 2 - I
epsilon_mean = (|epsilon_11| + |epsilon_22| + |epsilon_12|) / 3
```

This second value is used only by **Paper strain projection**. It does not
replace the maximum-principal-strain cutoff above.

Every retained candidate already satisfies that cutoff. Within one angular
match, v_ase ranks by the larger host/guest area ratio first, the sum of both
areas second, and residual strain third. The proposed cell is therefore the
smallest admissible physical common cell rather than a larger zero-strain
alternative.

For general oblique cells, v_ase performs a bounded search over 2D Hermite
normal-form integer supercells and Gauss-reduces their boundaries. Independent
host/guest lattices may use different primitive-cell area multipliers. For
same-lattice hexagonal and square cells it also uses analytic commensurate
families, which reaches useful small angles without enumerating millions of
generic supercells.

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

`Commensurate atoms` is disabled by default. Enabling it starts the bounded
search and opens the angle/area/strain graph. Commensurate rotation is always
global Z; normal free rotation remains available when the workspace is off.

- Distinct host, guest, and common-cell outlines remain visible while the guest
  rotates.
- The Plotly graph places rotation angle, area ratio, and residual strain on
  separate axes; a live angle plane and nearest-candidate marker track motion.
- The graph selector switches to **Paper strain projection**, which plots mean
  absolute strain against the actual host-plus-guest atom count and colors
  points by rotation angle.
- The current magnetic match is amber and its ray is prefixed with `SNAP`.
- The Structure panel reports both integer matrices, crystallographic notation,
  active-target strain, and separate host/guest area multipliers.
- The unchanged `0 deg` identity is included, so enabling snap never rotates a
  structure before the pointer or numeric angle actually moves away from zero.
- `Magnetic angle snap` independently enables or disables attraction.
- Magnetic snapping is disabled by default, so the guide never changes a
  rotation unless the user explicitly enables snapping.
- `Snap range / deg` controls the angular capture distance.
- `Max lattice index` controls the analytic search depth; the default `32`
  includes the `1.050121 deg` hexagonal candidate.
- `Max area ratio` bounds both host and guest integer cells. Its default is
  `16` and its explicit interactive maximum is `128`; no candidate above the
  requested limit is proposed or expanded.
- Cells-only preview is the default. Optional atom preview adds opaque core
  atoms, one primitive-cell halo, and bonds that cross the proposed boundary.
- Same-lattice mode requires selected rotating atoms. Host/guest mode loads an
  independent guest whose angle and offset move the full guest structure.

Turning magnetic snap off leaves every angle continuously editable while
keeping the scientific guide visible. Unlike the removed bond-strain guard, no
rotation is colored invalid or blocked at commit.

The analytic same-lattice hexagonal candidates are identical for graphene and
an ideal hexagonal h-BN primitive cell because the angle family depends on
lattice geometry, not chemical species. Python regression tests verify every
`(m,m+1)` point through `(31,32)`, including `21.786789`, `13.173551`, and
`1.050121` degrees, with zero boundary strain. A second basis-invariance test
rewrites an oblique lattice with a determinant-one integer transform and
requires the same zero-strain result.
For bounded host/guest search, another regression compares the accelerated
descriptor/tree path with complete enumeration through area ratio 5 and
requires identical canonical angle, area, and strain candidates.

The separate graphene/Cu(111) files and machine-readable expected values are
in [`examples/commensurate_host_guest`](../examples/commensurate_host_guest/README.md).
The complete equations, validation scope, and measured search bounds are in
[`commensurate_validation.md`](commensurate_validation.md).

## Proposed Common Cell And Boundary Shell

When the workspace finds an admissible candidate, v_ase constructs a separate
common-cell proposal immediately. It is not the ordinary `Replicate cell`
display setting and does not wait for the final rotation commit.

Let `P_h` and `P_g` be the 3 x 3 row-vector matrices obtained by embedding the
two integer matrices into their respective periodic axes. In the default guest-
strain construction, the host uses `P_h H_h`; the guest uses `P_g H_g`, receives
the rigid Z rotation and residual in-plane deformation `D_g`. Both therefore
share

```text
H_common = P_h H_h
```

The proposed-cell core atoms are opaque. For inspection only, v_ase also
enumerates one primitive-cell layer outside every 2D boundary. That muted shell
is not part of `H_common`; it exists so bonds crossing the proposed periodic
boundary are visible instead of ending at the cell line. Bond inference uses
the same active element/label cutoffs as the base structure and includes only
pairs with at least one endpoint in the opaque core.

The proposal panel reports both integer matrices, area ratios, boundary strain,
cell lengths/angle, and symmetry-reduced crystallographic notation such as
`(sqrt(7) x sqrt(7)) R19.11 deg`. The renderer preserves the current viewing
direction, frames the complete core and shell, and restores the previous
camera if the proposal is dismissed.

**Set Suggested Cell as Structure** materializes the validated common cell as
an ASE `Atoms` object. Fixed atom and supported directional constraints are
replicated. Cross-layer Hookean constraints and point/plane Hookean anchors are
rejected rather than guessed. Materialization is currently restricted to one
structure without volumetric grids: a trajectory requires a declared
frame-to-frame layer mapping, and a volumetric field requires a declared
layer-specific affine transform. The preview remains available when those
conditions prevent materialization. The graph's save icon exports angle,
matrices, area, strain, and the cited search references as CSV.

## XY Registry After Cell Matching

Commensurability closes the periodic boundary but does not choose the best
relative in-plane origin. v_ase therefore keeps registry analysis separate. For
a selected movable layer it scans one fractional XY period and displays either
a covalent-radii-scaled short-contact score or the normalized RMS mismatch of
enabled interfacial label-pair distances. Lower values mean less geometric
penalty; neither score is a stacking energy.

While the registry map is active, `G` is restricted to XY and its marker follows
the current periodically wrapped translation. The map and CSV retain fractional
coordinates, Cartesian shifts, selected indices, grid dimensions, and metric
definition. An energy-based optimum still requires an external electronic-
structure or force-field calculation.

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
for two components and only becomes the editable structure after the explicit
materialize action.

## References

- P. Lazic, ["CellMatch: Combining two unit cells into a common supercell with minimal strain"](https://doi.org/10.1016/j.cpc.2015.08.038), Computer Physics Communications 197, 324-334 (2015).
- D. S. Koda et al., ["Coincidence Lattices of 2D Crystals: Heterostructure Predictions and Applications"](https://doi.org/10.1021/acs.jpcc.6b01496), Journal of Physical Chemistry C 120, 10895-10908 (2016).
- D. Stradi et al., ["Method for determining optimal supercell representation of interfaces"](https://doi.org/10.1088/1361-648X/aa66f3), Journal of Physics: Condensed Matter 29, 185901 (2017).
- J. M. B. Lopes dos Santos, N. M. R. Peres, and A. H. Castro Neto, ["Continuum model of the twisted graphene bilayer"](https://doi.org/10.1103/PhysRevB.86.155449), Physical Review B 86, 155449 (2012).
- R. Bistritzer and A. H. MacDonald, ["Moiré bands in twisted double-layer graphene"](https://doi.org/10.1073/pnas.1108174108), PNAS 108, 12233-12237 (2011).
- J. S. Dai, ["An historical review of the theoretical development of rigid body displacements from Rodrigues parameters to the finite twist"](https://doi.org/10.1016/j.mechmachtheory.2005.04.004), Mechanism and Machine Theory 41, 41-52 (2006).
