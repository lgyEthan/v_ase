# Commensurate interfaces and registry

## Commensurate cells

Inspect both cells, periodic directions and intended host/guest planes. Discover
the commensurate search parameters instead of guessing integer matrices. This is
a bounded coincidence-lattice search, not a proof of the unrestricted global
optimum or energetic stability. Report the search bounds, integer transforms,
residual strain and which layer is strained.
Acceptance uses maximum principal-stretch mismatch, not the optional mean
paper-strain plot. The HNF search uses 20 finite determinant-one basis
correspondences and descriptor screening; do not call it an exhaustive search
over all integer bases. Same-lattice hexagonal search uses the documented
analytic family; an equivalent skew basis is reduced before classification.

Choose a candidate from the returned results. Preview coordinates/cell and atom
count before materialization. Base atom IDs and proposal row indices differ;
read the proposal metadata. `vase_scene_snapshot(sections=["preview"])` returns
the displayed proposal atoms and bonds. Filter `components` by host/guest/lattice;
use `preview_offset`/`preview_bond_offset` and the scene fingerprint for pages.
Preserve host/guest ownership and constraints.
Tilted unsupported host/guest planes must be rejected rather than projected flat.

## Registry maps and relaxation

A rigid (hkl) translation uses the actual lattice-plane basis. Inspect returned
periodic axes, Cartesian basis and fractional coordinates. The selected layer
must move as one rigid component; its internal coordinates and the host remain
unchanged. A geometric short-contact or bond-strain metric is not a calculated
DFT energy surface. Keep that distinction in captions and conclusions.
Atom indices and grid dimensions must be finite integers; fractional or Boolean
indices are errors, never requests to round to another atom. Use integer hkl.

Start/stop/finish/cancel registry relaxation are explicit lifecycle actions.
The current optimization can advance revisions; stop tools document their guard
exception. Finish or cancel before applying unrelated physical operations.
Export the candidate/registry CSV with the search/metric settings and references.
