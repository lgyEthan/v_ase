# Atomic and molecular insertion

## Specify the preparation problem

Choose atom species or molecules, counts/density, accessible region and seed.
Inspect the insertion-domain and pair-cutoff catalogs. Distinguish ordinary
random placement, bounded homogeneous placement and subsequent overlap removal.
A correlated homogeneous configuration is not an ideal Poisson distribution.
A fixed seed controls a documented stochastic preparation, not physical sampling.

## Repulsion and boundaries

Repulsion cutoffs are independent of displayed bonds. Inspect absolute/scaled
mode, reference basis, coefficient, periodic/MIC treatment and boundary region.
Periodic repulsion includes relevant self images; conservative forces apply to
the defined overlap energy. An overlap-free endpoint is not thermal or energetic
equilibrium under a realistic interatomic potential. Preserve fixed host atoms.

For molecules keep rigid geometry during placement; density depends on actual
accessible volume and molecule count/mass. Region unions, exclusions and periodic
wrapping must match the requested physical geometry. Stage insertion, inspect
realized counts/distances and metadata, then finish or cancel. Report a bounded
attempt limit or infeasible packing instead of silently reducing the request.

Batch insertion does not create mismatched trajectory topologies. Use a standalone
frame when needed. Discover dedicated scatter/relax/stop/finish tools; a figure
scene patch never inserts atoms or starts optimization.
