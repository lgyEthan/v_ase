# Volumetric data

## Scientific meaning and coordinates

Inspect dataset ID, source quantity/units, shape, origin, cell, PBC, precision and
frame association. A synthetic signed field is not DFT charge or a wavefunction.
Voxel data stays in the backend; do not request or print complete grids to style
an isosurface. Signed fields may need positive and negative surfaces; density is
not automatically a signed wavefunction. Preserve units and provenance.

## Isosurfaces and sections

Use discovered show-volumetric tools with explicit level, signed/single mode,
step size, smearing, smoothing, colors and opacity. Smearing is in voxel units;
level must cross the displayed field range. A frame can lack one signed crossing.
Inspect readiness/errors rather than pretending both surfaces were generated.
An isosurface is limited to 2,000,000 triangles. If it exceeds the limit, use a
coarser step size or a justified isovalue; do not silently change scientific data.

A section plane is defined by nonzero reciprocal-space hkl and signed Cartesian
offset in Angstrom along the normalized Cartesian normal. These coordinates must
use the actual cell; hkl is not generally the Cartesian normal. Use stable dataset
and plane IDs. Plane resolution and scalar colormap/range are presentation choices.
The typed operations validate plane IDs and compatible edits.

Plane selection is separate from atom selection. Deselect with
`vase_select_volumetric_planes(plane_ids=[])` if deselection is intended.
Publication export uses a neutral perimeter independently of selection;
`include_plane_borders=false` removes it. Never add/delete a dummy plane to change
the border. A scene patch can replace the explicit plane specification list.

## Combining fields

`combine-volumetric` requires matching grid dimensions, cell, origin, PBC,
quantity/units and endpoint conventions. Coefficients form a linear combination;
`result_name` names the result. Accumulation uses float64 slabs; choose retained
precision deliberately. A difference field is meaningful only with justified
alignment and compatible physical definitions. Frame association must remain
correct after combination or trajectory changes. Removing a dataset changes the
document; it is not necessary for a visual-only change.
