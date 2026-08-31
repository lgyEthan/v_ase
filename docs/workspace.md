# Workspace model

Understanding the workspace, document, and mode boundaries prevents accidental
cross-document edits and explains when v_ase materializes large trajectories.

## Workspace and documents

One browser workspace can contain multiple document tabs. Each tab maps to an
independent backend editor session with its own:

- original and working ASE structure;
- source, virtual, and relaxation trajectory state;
- current frame and selection;
- camera, rendering, labels, atom/bond appearance, and analysis state;
- calculator and constraints;
- undo/redo history;
- volumetric datasets; and
- collaboration revision and project output.

The **+** tab action creates an empty document. **Open** can replace the active
document, append frames to its trajectory, or create a new tab. Inactive
document iframes suspend rendering and movie playback, although a backend
calculation already in progress can continue.

## View and Edit

### View mode

View is the default for a loaded file and is optimized for inspection:

- camera navigation and axis views;
- click, box, label, and replica selection;
- ordered geometry and detailed single-atom inspection;
- trajectory scrubbing/playback;
- appearance, bonds, supercells, wrapping, and visual translation;
- analysis and all non-mutating exports.

View mode does not attach the fallback repulsion calculator. For indexed
XDATCAR, ASE trajectory, and compatible large LAMMPS sources, it can request
only the current frame rather than materializing the entire trajectory.

### Edit mode

Edit adds physical mutation workflows:

- `G`, `R`, and physical `S` transforms;
- atom/molecule creation, deletion, duplication, copy, and paste;
- cell and topology changes;
- constraint editing;
- calculator configuration and relaxation;
- structure-aware undo and redo.

Switching a lazy trajectory to Edit materializes all required frames first.
This is necessary because topology changes and trajectory-wide physical
operations need editable ASE objects rather than a view-only frame source.

### Empty launch behavior

`v_ase gui` with no file creates an empty **Edit** document. Define a finite
cell under **Structure > Cell & Replication** when building a periodic model,
then use **+ Add atoms** or **Build with ASE**.

## Original, working, and displayed state

v_ase never mutates the caller's original Python `Atoms`. Each document owns a
working copy. A browser transform previews displayed coordinates immediately,
then the backend validates and commits the operation and returns authoritative
coordinates.

Several visual operations deliberately do not change ASE coordinates:

- camera motion and projection;
- visual translation/alignment;
- displayed supercell replication in View;
- atom radius, opacity, color, material, and visibility;
- bond style and lighting;
- Render Area composition.

Physical operations such as translation, rotation, scaling, delete, add,
wrap, committed supercell construction, or relaxation do change the working
ASE object.

## Selection identities

Each atom has an ASE chemical **TYPE** and may have a separate visual **LABEL**.
TYPE controls element defaults and scientific interpretation. LABEL controls
group selection, appearance rows, and label-pair bond/repulsion rules. Repeated
VASP species blocks and custom extxyz/LAMMPS identities can therefore remain
visually separate without inventing new chemical elements.

In View, a displayed supercell replica is a distinct visual selection and can
be hidden or measured at its displayed position. In Edit, replicas resolve to
their unique base atom so a periodic image cannot become an accidental second
editable atom.

## History boundary

History records committed user actions, including compatible visual settings.
A confirmed transform, applied setting group, placement batch, or completed
relaxation start is one action. Continuous visual inputs are debounced. Camera
navigation is excluded so coordinate undo is not buried under orbit events.

Active Add Atoms sessions add a second safety boundary: Cancel restores the
exact pre-session baseline; Finish commits the accumulated staged content as a
single session result while individual placement batches remain undoable during
the session.

## Project restoration

Replacing a document or opening a new tab with `.vase`/project HTML restores
the complete saved state. Appending the same file to a trajectory imports only
its selected structure frames and keeps the receiving document's visual state.

See [Data input and documents](data-input.md) for the complete opening matrix.
