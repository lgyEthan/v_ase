# Radial distribution functions

## Choose the observable

Use the discovered RDF operation with cutoff, bins and intended pair selection.
Specify whether the curve describes all atoms, active displayed pairs or selected
atoms. Visual bond choices can alter an active/selected pair filter but do not
alter the underlying interatomic distances. Verify the selected labels/elements
and the actual frame before calculating.

## Periodic and finite normalization

Fully periodic three-dimensional systems use bulk RDF normalization. Finite,
nonperiodic structures use an unordered-pair distance probability density.
Do not label a finite-cluster histogram as a bulk g(r) or expect its tail to be 1.
Reduced periodicity and finite cells need their documented normalization/limits.
The backend counts periodic images within the requested cutoff; it does not
silently reduce the cutoff to a fixed neighbor-cell shell or MIC radius.

Report cell/PBC, cutoff, binning, pair convention and the normalization actually
returned. Bins are numerical resolution, not uncertainty estimates. A single
snapshot is not a statistical ensemble; trajectory averaging needs an explicit
frame range and interpretation. Use the returned scientific diagnostics.

## Export

Use `vase_export_rdf_csv` after confirming the result/frame/filter. Preserve total
and partial curve definitions. An image can illustrate the curve; the CSV and
scientific parameters are the reproducible data. Do not load the full plot payload
just to confirm that calculation finished; focused analysis/readiness is enough.
