# Commensurate interfaces and registry

## Commensurate cells

For `vase_rotate_to_commensurate`, select a nonempty proper subset representing
the layer to rotate. At least one unselected host atom must remain in the same
document; selecting all atoms is rejected. Load a separate guest with
`vase_load_commensurate_guest` when the host and guest start in different files.

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
Running a mode starts asynchronous optimization. Inspect `registryRelaxation`
in the analysis state until `is_relaxing` is false; completion does not Finish
the mode. A delayed structure read or start response cannot revive an older
running state. The completed mode can be run again before Finish or Cancel.
Server teardown cannot consume another viewer's completion notification; each
server delivers ordered updates on the event loop that owns its sockets.
Clearing a registry movie rejects queued updates from the discarded run while
keeping the mode active and the chosen geometry intact.
The current optimization can advance revisions; stop tools document their guard
exception. Finish or cancel before applying unrelated physical operations.
Export the candidate/registry CSV with the search/metric settings and references.

In the desktop editor, the inspector and nearby camera tools move together.
Opening or resizing the inspector preserves coordinates, camera direction and
pixels per Å while the actual stage gains space.
An open color map list handles Escape locally and restores its trigger.
Native selects retain their platform option list and keyboard behavior.
