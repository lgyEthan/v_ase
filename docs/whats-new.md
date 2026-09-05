# What is new in 0.3.1

Version 0.3.1 audits scientific calculations, removes avoidable Python work in
repulsion, and organizes the guide around individual features.

## Atomic distributions and repulsion

Mixed species are assigned to a seeded permutation of sites, avoiding grid-order
segregation and maximin-rank bias. The GUI explains that homogeneous refinement
applies through 1,024 atoms or molecule anchors; larger batches use a bounded
low-discrepancy sequence. See [atomic distributions](atomic-distributions.md).

Default repulsion forces now agree with the reported harmonic energy. Periodic
self images and periodic copies of rigid molecules contribute correctly. Numeric
onset distances and radius-basis changes affect the actual pair model. A NumPy
coincidence-grouping optimization reduced measured kernel time by 1.6–3.2× in
our documented cases; this is not a GPU or whole-application speed claim.

## Commensurate cells

Tilted periodic planes are rejected before projection can hide out-of-plane
mismatch. The GUI explains maximum principal strain, and the guide distinguishes
that acceptance criterion from the basis-dependent paper-style strain display.
The [periodic-interface guide](periodic-interfaces.md) now gives a complete
bounded-match procedure and explains the published-method adaptation.

## RDF and volumetric processing

RDF includes its exact final cutoff edge, validates integer bins and finite
geometry, and has a [dedicated guide](rdf.md) covering finite-N normalization,
partial curves, bulk versus finite systems, and Python-to-CSV output.

Finite endpoint-inclusive grids now use trapezoidal integration; periodic
closing planes are still counted once. Field combinations accumulate in FP64
slabs before final storage conversion, reducing cancellation errors without
allocating a full additional FP64 grid. Read the [field guide](volumetric-guide.md)
for units, precision, integral conventions, and the limits of display smoothing.

## Trajectory properties and project reopening

Stored forces, tags, and charges now follow the displayed source frame even
when force arrows are hidden. Scalar/vector analysis retains stored calculator
results without evaluating a calculator. Saved visible field planes are sampled
before initial readiness, so reopening a project includes its planar raster in
the first render. Commensurate previews have an explicit **Fit Preview in View**
control, correct proposal-angle reporting, and CSV area-membership flags.

## Reliable automation and readable documentation

`combine-volumetric` uses `resultName` for its output label. Previous examples
used duplicate `name` keys, which could overwrite the command selector. A CLI
regression checks the actual output, and documentation JSON now rejects duplicate
keys. During placement, `calculator.detailsScope` identifies the document
calculator and `placementDetailsPath` directs agents to `addAtoms` for the
active temporary optimizer's settings.

Long pages now have local feature navigation. Volumetric JSON examples are
separate load, surface, plane, style, and combination tasks. The Python API
starts with a runnable example and keeps its full signature in a reference
section. README media and the canonical Skill follow the same release.

## Upgrading

```bash
python -m pip install --upgrade "v_ase-gui==0.3.1"
```

Seeded mixed placements and default repulsive trajectories can differ from
older releases because the corrected algorithm changes the result. An explicit
Python `max_force_norm` retains legacy limiting, with its documented
nonconservative meaning. Update semantic field naming to `resultName`.

The [scientific validation record](scientific-validation.md) explains the
independent checks and their interpretation boundaries.
