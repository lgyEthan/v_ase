# Periodic cells and interfaces

v_ase distinguishes display replication, physical supercell construction,
bounded commensurate-cell matching, and rigid registry analysis. They solve
different problems and should not be substituted for one another.

## Cell and periodic boundary conditions

Under **Structure > Cell & Replication**, edit the complete 3×3 cell and the
three PBC flags. Setting a cell does not scale Cartesian atom coordinates. Wrap
maps atoms into periodic directions of their own current frame.

For a trajectory-wide physical operation, every frame is validated and uses
its own cell and PBC. The active frame's lattice is never copied onto the other
frames as a shortcut.

## Displayed and physical supercells

### Display replication

The displayed supercell repeats visual instances for inspection, measurement,
styling, and composition. It is saved as a display setting. In View, replicas
can be selected and hidden independently. In Edit, replica selection resolves
to the unique base atom.

Display replication does **not** change `len(atoms)`, coordinates, constraints,
or the exported physical structure.

### Physical supercell

Use the physical replication/commit action when the ASE object must contain the
repeated atoms. Diagonal repetitions and general integer 3×3 supercell matrices
are validated against cell rank, atom-count limits, arrays, labels, and
supported constraints. This is a topology-changing Edit operation and is added
to history.

## Visual and physical translation

- Visual translation changes only where the rendered scene appears. It can be
  Cartesian or fractional and is stored with display settings.
- Physical `translate-all` changes ASE coordinates on every applicable frame
  without changing the cell. Fractional vectors use the full non-orthogonal
  cell matrix.

Use visual translation for composition/alignment and physical translation when
the saved coordinates themselves must move.

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

## Registry maps

Registry analysis translates one rigid selected component over a periodic
`(hkl)` plane and evaluates a geometric metric on a bounded 2D grid. Available
metrics include current short-contact and bond-strain screens. The result keeps
the exact plane basis and Cartesian translations so a point can be reproduced
or exported to CSV.

These maps are geometric screens, not potential-energy surfaces. Their meaning
depends on the selected component, plane, pair cutoffs, reference bonds, and
grid resolution.

## Rigid registry relaxation

After choosing the moving component, v_ase can optimize one shared rigid
translation in either:

- a compatible periodic `(hkl)` plane; or
- bounded Cartesian x/y/z translation.

All selected atoms preserve internal geometry. The optimization timeline can
be scrubbed before Finish or Cancel. Plane and Cartesian modes have explicit
bounds; invariant-geometry and finite-difference checks protect the rigid
contract.

Use **Finish** to commit the selected result. **Cancel** restores the exact
pre-workflow structure. Stopping leaves the workspace and current result open
for inspection.

![Registry map and rigid translation](assets/readme_registry_map.png)

## Measurement across replicas

For two displayed atoms, v_ase reports the direct displayed distance and the
minimum-image distance when defined. If a replica is involved, it can also show
the distance after both atoms are mapped into the original unit cell. Angles
and torsions use the displayed Cartesian coordinates only.

This keeps the meaning of a clicked periodic image explicit instead of silently
replacing it with the nearest base atom.

## Export and verification

- `commensurate-csv` exports candidates, integer matrices, area ratios,
  strains, and search references.
- `registry-csv` exports the complete grid, lattice basis, Cartesian vectors,
  and metric values.
- Project/HTML output preserves the current preview and visual state as
  supported.

After materializing a cell, verify atom count, cell vectors, PBC, constraints,
and boundary continuity in the exact saved structure—not only in the preview.
