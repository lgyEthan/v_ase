# Unit cells, PBC and supercells

Set boundary conditions, repeat a physical structure or display more periodic
images. Open **Structure > Cell & Replication**. Choose the operation according
to whether the exported ASE structure should change.

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

## Cell operations: choose the correct one

| Goal | GUI/API state | Changes ASE data? |
| --- | --- | --- |
| Show repeated images | **Replicate cell** / `display.supercell` | No |
| Visually offset atoms and overlays | translation controls / `display.translation` | No |
| Put selected COM at scene origin | **Selection COM to Origin** | No |
| Move every atom but keep cell | **Apply Translation** / `translate-all` | Yes |
| Wrap into the cell | **Wrap Atoms Into Cell** / `wrap` | Yes for the affected frame(s) |
| Make diagonal repeats the real cell | **Set Supercell as Cell** / `set-supercell` | Yes |
| Apply a general integer cell transform | **Cell Transform** / `make-supercell` | Yes |
| Replace the cell without moving atoms | **Set Unit Cell** / `set-unit-cell` | Cell/PBC only |

In View, wrap affects the active displayed frame. In Edit, trajectory-wide
physical cell and translation operations operate on editable frames and are
recorded as one user action. General non-diagonal cell transforms are rejected
while volumetric grids are loaded because preserving those samples would
require an explicit interpolation choice.


## Example: compare displayed and physical repeats

Download {download}`graphene_hbn_commensurate.traj <assets/examples/graphene_hbn_commensurate.traj>`. Open it with **File > Open**, or run this in the folder containing the download:

```bash
v_ase gui graphene_hbn_commensurate.traj
```

1. In View, set displayed replication to `2 × 2 × 1` and inspect the cell edges.
2. The physical atom count is unchanged: these are visible periodic copies.
3. Return display replication to `1 × 1 × 1`, switch to Edit and apply a physical
   diagonal supercell matrix with entries `2, 2, 1`.
4. The physical atom count is now four times the input count, and both in-plane
   cell vectors double. Export the structure to retain that physical repetition.

```{figure} assets/readme_commensurate.png
:alt: A periodic bilayer provides a clear input for cell and replication exercises.

A periodic bilayer provides a clear input for cell and replication exercises.
```
