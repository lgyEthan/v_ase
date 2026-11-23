# Structures

## Load and identify

Discover `files`, `load-structure` and `append-structure` with bounded tool search.
Use returned paths below the GUI launch directory. Load replaces the document;
use a new workspace tab or explicit replacement intent. Append adds frames/fields
and does not import an appended project's appearance. Project files restore the
human-editable scene and clear the previous document's commensurate preview;
prior preview visibility must not hide the restored atoms or bonds.
Labels such as O_1 remain distinct from chemical symbols.
CIF auto detection and the explicit `cif` reader preserve cell/PBC and symmetry
expansion. An unknown expanded H-M name with an explicit symmetry table uses
that table without a database-name guess; missing operations still report an
error. Original labels remain in `cif_site_label`. O-H1 is an oxygen site label,
not a hydrogen coordinate or evidence that hydrogen atoms should be added.
`load-settings` restores a saved visual preset without replacing coordinates.

Read focused structure state for counts, identities, cell, PBC and constraints.
Include positions/properties only when the requested edit needs them. A frame or
topology change invalidates cached indices; inspect the current identities again.

## Physical editing

Dedicated tools cover atom insertion/deletion, identity changes, duplication,
translation, rotation, scaling, wrapping, unit-cell edits and ASE bulk builders.
Use `duplicate-selection` for an explicit copy of the selected physical atoms.
Use Edit mode for physical work. Never enter Edit merely to change a figure:
mode transitions can attach the configured calculator. Preserve constraints
unless the user asks to alter them. Surface placement and chemical equilibrium
are separate objectives.

A physical supercell materializes atoms and transforms applicable scientific
metadata. Display repetitions change only the figure; use them for a repeated
visual motif. Inspect cell/PBC and transformations before materialization.
ASE/backend coordinates after the edit are authoritative; do not infer positions
from the rendered spheres. Use operation schemas for supported constraint and
metadata transformations rather than assuming every arbitrary tensor is handled.

Rigid translation retains constraints but bypasses their per-atom projection,
including when the compatibility `applyConstraints` field is true. Use
`move-selection` when motion must obey FixAtoms, FixedLine or FixedPlane.

## Bulk structures

Use `vase_bulk_catalog` and `vase_bulk_preview`, choose a supported ASE crystal convention and
inspect the proposed cell/count before replacing an existing structure. Primitive,
orthorhombic and cubic cells can differ. Calculator/labels/constraints need an
explicit scientific decision after a topology-changing build.

## Human move and rotation controls

In Edit, `G` then `X`/`Y`/`Z` and a number requests an axis displacement in Å.
`R` uses degrees about the chosen pivot; `S` scales coordinate spacing. These
axes are global Cartesian directions, not lattice rows. ASE constraints can
project the request; verify committed positions. A FixedLine can project a
Cartesian request onto an oblique line. Pointer increments do not quantize typed
numbers; commensurate magnetic snapping can affect rotation angles separately.
FixedLine guide length and thickness follow mapped atom radii immediately,
including interpolated frames; saving or reopening must not change their size.
Near-zero mapped radii also shrink the guide, preventing orphaned line marks.
Background structure reads and appearance rebuilds preserve the active preview;
older reads cannot overwrite a newer committed edit. Escape restores the
starting coordinates even if a rebuild occurred. Enter confirms the preview asynchronously; wait for the
committed backend state before verifying coordinates or starting another edit.

The `selection` rotation/scaling pivot is the arithmetic coordinate centroid,
despite the GUI's “Selection COM” label. It is not mass-weighted. `active` uses
the last selected atom; `origin` uses [0,0,0]; `cell` uses the cell center. Do not
confuse this with the separate mass-weighted visual COM-to-origin operation.
The ferrocene fixture uses top-ring indices 1–10 and Fe #0 selected last. Rotation
about Fe leaves Fe unchanged but does not create an ASE fixed-atom constraint.

The user manual has independent Move, Rotate and Constraints pages, with exact
input downloads and sampled GIF stills. A sampled frame is not evidence of an
exact numerical endpoint; inspect the semantic coordinates for that check.
