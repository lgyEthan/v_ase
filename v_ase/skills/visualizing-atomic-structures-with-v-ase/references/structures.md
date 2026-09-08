# Structures

## Load and identify

Discover `files`, `load-structure` and `append-structure` with bounded tool search.
Use returned paths below the GUI launch directory. Load replaces the document;
use a new workspace tab or explicit replacement intent. Append adds frames/fields
and does not import an appended project's appearance. Project files restore the
human-editable scene. Labels such as O_1 remain distinct from chemical symbols.
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

The `selection` rotation/scaling pivot is the arithmetic coordinate centroid,
despite the GUI's “Selection COM” label. It is not mass-weighted. `active` uses
the last selected atom; `origin` uses [0,0,0]; `cell` uses the cell center. Do not
confuse this with the separate mass-weighted visual COM-to-origin operation.
The ferrocene fixture uses top-ring indices 1–10 and Fe #0 selected last. Rotation
about Fe leaves Fe unchanged but does not create an ASE fixed-atom constraint.

The user manual has independent Move, Rotate and Constraints pages, with exact
input downloads and sampled GIF stills. A sampled frame is not evidence of an
exact numerical endpoint; inspect the semantic coordinates for that check.
