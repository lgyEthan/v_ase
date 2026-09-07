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
