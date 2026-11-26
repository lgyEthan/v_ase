# Radial distribution functions

## Choose the observable

Use the discovered RDF operation with cutoff, bins and intended pair selection.
Specify whether the curve describes all atoms, active displayed pairs or selected
atoms. Visual bond choices can alter an active/selected pair filter but do not
alter the underlying interatomic distances. Verify the selected labels/elements
and the actual frame before calculating.

## Periodic and finite normalization

Use bulk RDF normalization for a fully periodic 3D system. A slab
or wire uses periodic-image neighbor density per atom per Å and reports
`periodic-pair-distribution`. A finite structure uses unordered-pair distance
probability density. The calculation includes every allowed periodic image
inside the cutoff, while using distances in three Cartesian dimensions.
`use_pbc` defaults to `true`. Pass `use_pbc=false` to `vase_calculate_rdf` for
stored Cartesian distances with finite pair normalization.

Report cell/PBC, cutoff, binning, pair convention and the normalization actually
returned. Bins are numerical resolution, not uncertainty estimates. A single
snapshot is not a statistical ensemble; trajectory averaging needs an explicit
frame range and interpretation. Use the returned scientific diagnostics.

## Export

Use `vase_export_rdf_csv` after confirming the result/frame/filter. Preserve total
and partial curve definitions. An image can illustrate the curve; the CSV and
scientific parameters are the reproducible data. Do not load the full plot payload
just to confirm that calculation finished; focused analysis/readiness is enough.

The human plot displays r/Å and the actual observable. **Move graph to
viewport** and **Dock graph below the viewport** move the same plot, including
registry and commensurate plots. A floating plot supports dragging, resizing,
and CSV. Drag the lower-right grip to snap the moving edges to the other
floating graph. Click a Distribution or Energy graph to open the same
**Graph settings** inspector. Choose **Data series** to edit the curve name,
line and markers. Grid, legend visibility, fonts, tick-label visibility and
number formatting apply to the whole graph. Valid **Axis limits** apply as you
type, including after recalculation. A blank field uses Auto. The
`vase_apply_scene` display field `analysis_plots` accepts `axes` per plot
with `x_min`, `x_max`, `y_min` and `y_max`.
The 2D commensurate projection uses `projection_axes`. An explicit null
restores Auto. For `analysis_plots.rdf.style.series`, use `total` or the exact
pair key from the result, such as `Cu_2|O`. A partial series patch preserves
other curve styles. Read the display schema for font and tick fields. A
one-to-one label rename preserves the result and moves its pair styles to
the new key. Merges and frame-specific assignments require recalculation.

For HTML, float the distribution before exporting with `include_graph`.
Verify the preview, poster, and offline interactive plot against the analyzed
frame. The view retains the captured data, bounds, style, and placement.
