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
Boundary forces use Cartesian distance to the feasible domain closure, including
skew faces and overlapping exclusions. Tied nearest faces and exact atom overlaps
have no unique derivative. A prohibited box excludes its intersection, not each
axis slab separately. Hard boundary projection is reflected in the returned
positions, energy and forces. Status `steps` means the force criterion was not met.

For molecules keep rigid geometry during placement; density depends on actual
accessible volume and molecule count/mass. Region unions, exclusions and periodic
wrapping must match the requested physical geometry. Stage insertion, inspect
realized counts/distances and metadata, then finish or cancel. Report a bounded
attempt limit or infeasible packing instead of silently reducing the request.
Rigid molecules cannot combine with conflicting atomwise positional constraints.
Complex domains fail explicitly before staging: at most 4,096 candidate periodic
region images and 250,000 Boolean partition cells; projection is bounded to
2,000,000 component images. Simplify region geometry or explicitly change wrapping
after a limit error; never quietly change the requested domain.

Batch insertion does not create mismatched trajectory topologies. Use a standalone
frame when needed. Discover dedicated scatter/relax/stop/finish tools; a figure
scene patch never inserts atoms or starts optimization.
