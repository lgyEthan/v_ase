# Constraints and relaxation

## Preserve physical constraints

Inspect the backend constraint representation before moving atoms or changing
cell/topology. Fixed atoms, fixed lines and fixed planes constrain different
Cartesian degrees of freedom. Validate direction/normal vectors and cell-axis
conventions; do not replace directional constraints with FixAtoms for convenience.
Periodic replicas are references to base atoms; physical edits deduplicate them.

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
