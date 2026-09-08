# Commensurate cells and layer matching

Find a common periodic cell for a selected layer or a separate host/guest
structure. Open **Structure > Transform & Cell Match > Commensurate atoms**.
This is a bounded geometric search. Supply layer indices or select the intended
layer; v_ase does not decide which atoms belong to a physical interface.

## Choose the matching problem

| Input | Use |
| --- | --- |
| A selected layer in the current structure | Same-lattice rotation about global Z |
| A separate guest file | Load or Replace Guest Structure |

## Example: graphene host and MoS2 guest

Download {download}`graphene_host.extxyz <assets/examples/graphene_host.extxyz>` and {download}`mos2_guest.extxyz <assets/examples/mos2_guest.extxyz>`.

1. Open the graphene host. Turn on **Commensurate atoms**.
2. Use **Load or Replace Guest Structure** to load MoS2. Set the interlayer gap
   to 3 Å; this is guest minimum z minus host maximum z.
3. Set guest angle to 0°, maximum strain to 3%, maximum area ratio to 16, and
   strain target to Guest. Search and inspect the candidate table.
4. In the audited source, a primitive match has host/guest area ratios **7/2**,
   edges **6.50855 Å**, and an internal angle of **60°**. The earlier 0.3.3 search
   returned a doubled rectangular 14/4 cell at the same strain.
5. Select a row, inspect its strain and atom preview, then use **Set Suggested Cell as Structure** if you want a physical common cell. Check the resulting atom count,
   PBC and cell before export.

```{figure} assets/readme_commensurate_host_guest_match.png
:alt: Primitive graphene/MoS2 common-cell result in the audited source.

Primitive graphene/MoS2 common-cell result in the audited source.
```

```{vase-animation} assets/readme_commensurate_host_guest.gif
:alt: Host and guest cell-search animation
:fallback: assets/readme_commensurate_host_guest.png


```

The match controls residual deformation, not energy or experimental stability.
For search limits and independent checks, read [Commensurate validation](commensurate_validation.md)
and the [source audit](scientific-source-audit.md#commensurate-cells).


## Commensurate same-lattice rotation

The commensurate workspace searches bounded integer cell-boundary matches. It
can guide a rotation, preview a common cell, and materialize the selected
candidate. Search limits include integer index/area bounds and strain tolerance;
results are deterministic for the same inputs.

The guide is disabled by default. When enabled, it searches and displays
candidate angles, matrices, area ratios, cell geometry, and residual strain.
Magnetic snapping is a separate opt-in behavior.

This is a lattice matching operation, not an electronic-energy or adsorption
site search. Candidate strain values describe the selected cell mapping and
target convention.

## Separate host and guest lattices

Host/guest mode loads a second structure and searches a common two-dimensional
cell. Both periodic planes must align with global XY to numerical tolerance;
tilted cells are rejected rather than flattened by projection. A candidate
contains separate host and guest integer matrices, relative rotation, area
ratio, residual strain, and preview geometry.

Before applying:

1. Confirm the periodic plane and global axis convention.
2. Inspect both cell matrices and atom counts.
3. Choose the intended strain target rather than assuming one component is
   rigid.
4. Inspect boundary atoms/constraints in the preview.
5. Materialize only after the common-cell result is acceptable.

### Run a bounded match

Open the host in Edit, then **Structure > Transform & Cell Match**. Enable the
commensurate workspace and load the guest. Start with area ratio 16 and maximum
strain 1%; choose which side receives strain and inspect the cells-only preview.
If no candidate passes, increase the area ceiling or reconsider the physically
acceptable strain. The maximum interactive area ratio is 128.

Choose a candidate angle, inspect atom count and integer matrices, then enable
atom preview to check the interface. Interlayer gap is `guest min(z) − host
max(z)` in Å; it is a placement parameter, not a relaxed separation. Applying
the common cell creates actual ASE atoms and can be undone.

The camera stays where you put it when a preview appears. Use **Fit Preview in
View** to frame the complete parent-lattice window and optional atoms; the
semantic equivalent is `camera: {fit: "commensurate"}`. The surrounding halo
adapts to the preview window and is not always one primitive cell. For a
same-lattice twist, select only the guest layer and leave host atoms unselected.

CSV exports include the full plotted reference series, which can exceed the
current area ceiling. The `within_area_limit` column is 1 for candidates inside
that ceiling and 0 for larger reference cells. A plotted reference is not
automatically an admissible materialization candidate.

### Read the two strain measures

**Maximum strain / %** applies to `max(abs(singular_values(D) − 1))`, where
`D` maps the strained side onto the fixed side after rotation. It is independent
of a rigid coordinate rotation. The optional **Paper strain projection** shows
the mean absolute components of `sym(D) − I`; this small-strain descriptor is
basis-dependent and does not replace the acceptance criterion or estimate energy.

The search implements an HNF/reduced-basis adaptation of published integer-cell
matching methods, with Procrustes rotation and a finite orientation set. It is
not a line-by-line reproduction of the Stradi algorithm. It keeps the preferred
representative in each 0.01° angle bucket, so the plot is not an inventory of
every possible registry, strain sharing, or unbounded supercell.

The detailed mathematics, notation, and reference series are in
[Cell-aware rotation and commensurate angle guide](unit_cell_aware_rotate.md).
Numerical fixtures and search bounds are documented in
[Commensurate scientific validation](commensurate_validation.md).

![Host and guest commensurate-cell workflow](assets/readme_commensurate_host_guest.png)

