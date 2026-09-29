# Constraints and relaxation

## Preserve physical constraints

Inspect the backend constraint representation before moving atoms or changing
cell/topology. Fixed atoms, fixed lines and fixed planes constrain different
Cartesian degrees of freedom. Validate direction/normal vectors and cell-axis
conventions; do not replace directional constraints with FixAtoms for convenience.
Periodic replicas are references to base atoms; physical edits deduplicate them.
Constraint edits propagate by atom index to every loaded trajectory frame where
the index exists; they are not frame-local. Undo restores the full change.

Visualization-only work does not enter Edit mode or attach a calculator. If
physical relaxation is requested, confirm the intended calculator and constrained
component before starting. A configured repulsion calculator removes overlap;
it does not establish a realistic minimum-energy material structure.
`configure-calculator` changes the calculator parameters without starting it.

## Optimization lifecycle

Use start/stop and inspect the resulting trajectory/status. Stop tools can omit
an advancing revision but still require document identity. Ordinary mutations
retain both guards. Inspect state after a timeout before retrying; the process
may have started. Finish/cancel temporary insertion or registry sessions explicitly.

## Save and inspect

Keep constraints when exporting scientific projects. Some formats cannot encode
arbitrary directional constraints (for example certain POSCAR selective-dynamics
mappings); use the reported compatibility error and a preserving format rather
than dropping constraints. Scientific markings may remain in publication images;
selection outlines are a separate transient visualization.

## Read FixedPlane glyphs

Each atom has a filled, translucent pale cyan face oriented in its allowed plane,
from the atom boundary to an outer ring. Narrow, darker inner and outer rims
make its edges distinct from the face. Selection expands both rims by 0.18 atom radii: the radial span changes from
1.00–1.48 to 1.18–1.66, preserving face width and edge thickness around the
yellow outline. Actual depth and 30% face opacity resolve overlaps. Publication
hides selection and restores the nonselected ring geometry. There is no empty gap between atom and rim.
Face/rim/normal size and position share the same `atomVisualRadius` and position
updates as selection, including interpolated property radii, individual radius
scales, and label radii. Geometry is reused while these values animate. At zero
radius the marks disappear and return with the atom. Only selected or hovered
atoms show the blocked normal as dashes with X endpoints. Hover does not select. All geometry writes/tests actual scene
depth: a rear arc is hidden by its atom or a nearer neighbor, and a front arc
can cover the yellow selection outline. There is no camera-facing cyan atom
contour and no always-on-top overlay. The band has a thin rounded edge, so an
edge-on view stays legible without changing the physical plane orientation.
Each atom retains its own orientation, including during `G` and in flat 2D.
There are no scene-sized sheets or shared group planes. Objects > Constraints hides
all marks without removing physical enforcement. For a screenshot of yellow
selection, use `selection_appearance="interactive"`; publication output
suppresses yellow outlines while retaining scientific guides.
