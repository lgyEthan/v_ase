# Volumetric data

## Scientific meaning and coordinates

Inspect dataset ID, source quantity/units, shape, origin, cell, PBC, precision and
frame association. A synthetic signed field is not DFT charge or a wavefunction.
Voxel data stays in the backend; do not request or print complete grids to style
an isosurface. Signed fields may need positive and negative surfaces; density is
not automatically a signed wavefunction. Preserve units and provenance.

## Isosurfaces and sections

GUI: Style → Isosurfaces owns the surface definition. Analyze → Fields owns
import and combinations; Objects → Fields is a contextual view of the same state.

Use discovered show-volumetric tools with explicit level, signed/single mode,
step size, smearing, smoothing, colors and opacity. Smearing is in voxel units;
level must cross the displayed field range. A frame can lack one signed crossing.
Inspect readiness/errors rather than pretending both surfaces were generated.
A backend-extracted isosurface is limited to 2,000,000 triangles. If it exceeds the limit, use a
coarser step size or a justified isovalue; do not silently change scientific data.
Coarse meshes retain domain endpoints but may miss unsampled features. Mesh
smoothing fixes finite outer boundaries and changes display geometry only.
FP64 fields are centered on the requested level before FP32 marching cubes;
this preserves resolvable variations above a large baseline.

A section plane is defined by nonzero reciprocal-space hkl and signed Cartesian
offset in Angstrom along the normalized Cartesian normal. These coordinates must
use the actual cell; hkl is not generally the Cartesian normal. Use stable dataset
and plane IDs. Plane resolution and scalar colormap/range are presentation choices.
The typed operations validate plane IDs and compatible edits.
Endpoint-exclusive periodic slices interpolate the final voxel back to the first;
finite axes stop at their last stored sample. Preserve the dataset's convention.

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
Origins must agree within an absolute 1e-6 Å tolerance, independent of a common
translation; source precision and this alignment check are separate concerns.

## Display-only surface finish

Renderer → Quality accepts `display.isosurfaceInterpolation` (integer 0–8) and
`display.isosurfaceMeshSmoothing` (integer 0–100). These change a display copy of
the extracted mesh, not the isovalue or scalar dataset. Fairing runs before
subdivision; the renderer allows at most 8,000,000 resulting triangles per surface
and 12,000,000 combined. GUI controls are disabled without a visible isosurface.
Use Style → Isosurfaces to create/show one. See [water-surface.md](water-surface.md)
for progress, cancellation, recovery and scientific limitations.
