# Find your way around

The structure stays in a framed canvas. Open documents appear in horizontal
tabs at the top; Scene occupies the left sidebar and the selected tool the right.

## Workspace and documents

Each document has its own structure, trajectory, selection, camera, appearance
and undo history. Use **+** beside the tabs for a new document. Open files with
**File → Open** in the native desktop menu bar, or **… → File → Open** in a
browser. Native desktop tabs reorder horizontally; drag below the strip to move
a document into a new window. A destination preview appears before release;
Escape/pointer cancellation commits neither action.

When a document contains work, **Open in new tab** is the default for File → Open
and drag-and-drop. Replacing it or adding frames to its trajectory requires an
explicit selection. An empty tab opens a single file directly. Selecting several
files offers **Separate tabs** (one new tab per file) or **One trajectory** (all
files' frames in one new tab); existing documents stay open in either case.

The Scene toolbar button shows/hides the sidebar; it collapses by default at
1100 px or below. The independent inspector toggle controls the right panel.
Both buttons change their glyph and Show/Hide description with state. Hiding
Scene leaves the top tabs and v_ase logo available.

| Area | Use it for |
| --- | --- |
| Document tabs | Switch, close, reorder and create documents; inspect unsaved state. |
| Native menu / browser **…** | File, Edit, View, Preferences and Help commands; the desktop avoids a duplicate in-app menu. |
| Canvas palette | Select, measure, move, rotate, scale, orbit and add. |
| Scene sidebar | Actual scene objects, visibility, guides and optional overlays. |
| **Style** | Atoms, bonds, cell, polyhedra, water, isosurfaces, forces and Display & guides. |
| **Build** | Add atoms/molecules, transform, edit cells, constrain and relax. |
| **Analyze** | Measurements, distributions, displacements, fields and interfaces. |
| **Render** | Renderer, Image, Video, Interactive HTML and Geometry. |

**View only** and **Edit structure** are mutually exclusive access modes in the
outlined toolbar segment. Search and camera navigation never silently enable
physical edits. **Find tools…** (**⌘F / Ctrl+F**) searches every category and
command, even from Render. Clicking the inspector title lists only the current
category's tools. The category tabs sit above the inspector; the access-mode
segment belongs to the left side of the stage toolbar.
Results identify their category. **Camera** on the canvas groups presets,
rotation steps, grid and lighting; **Fit view** stays separate.

**Right-click** an atom, bond, cell edge or other viewport object to open
its actions. A separate section gives actions for a different atom selection.
Opening or dismissing the menu keeps that selection. Editing a label opens
the Selected atoms field, and blank space offers Add atoms & molecules.
Right-drag pans the viewport.

**Style → Display & guides** offers **Graphite** (neutral default), **Slate**,
**Stone** and **Moss**, independently of **System / Light / Dark**. Preferences
persist locally and update the entire workspace together. They change interface
surfaces and controls without altering the scientific background, atom colors,
lighting, camera or image export profile. Set the canvas background separately.

Expand an atom-label row for element, radius, opacity and material. Visibility
and selection remain independently usable without expanding it. Add atoms shows
XYZ coordinates. Constraints show the current selection scope and relevant
parameters. **Render → Image** exposes exact dimensions and framing immediately;
**Advanced render settings** contains shared lighting, quality and camera options.

Panel toggles commit canvas size once and animate only the panel surface. Resizing preserves coordinates, camera direction
and viewing scale, while the canvas gains real space. Narrow portrait windows
stack the inspector below the canvas; short landscape windows keep them beside
each other. Tool palettes remain scrollable and exact numerical input is retained.
Motion respects the system reduced-motion preference. The colormap list chooses
the side with room; Escape returns to its button and leaves the inspector open.
[Design and interaction contract](interface-design.md) · [Reference study](interface-references.md).

The inspector and analysis separators also support keyboard resizing: focus an
edge and use the arrow keys, or hold Shift for larger steps. Home/End chooses
the size bounds; double-click restores the default. Keyboard steps commit
immediately. Escape during a pointer/touch drag or an interrupted drag restores
its starting size. After a committed key step, Escape keeps that size and closes
the inspector. Resizing does not enter the structure's Undo
history. The bond label-column separator follows the same cancellation model.

Analysis results open below the canvas. Drag the top edge to resize that area.
On short windows, use **Back to viewport** to return from a plot to the structure.

## View and Edit

### View mode

Use **View** to navigate, select, measure, play trajectories, change appearance,
run analysis and export results without editing atomic coordinates.
Structure files normally open in this mode.

### Edit mode

Switch to **Edit** to move, rotate, add or delete atoms, change a cell, set
constraints or run relaxation. A large trajectory may take time to become
editable; wait for its loading indication to finish.

### Empty launch behavior

A new empty document starts in **Edit**. To build a periodic structure,
set a cell under **Style → Cell**, then use **Build → Add atoms**.
A saved project reopens in the mode it had when saved.

## Original, working, and displayed state

Changing camera position, atom size, colors or render composition affects the
presentation, not the physical structure. Moving atoms with **G**, rotating
them with **R**, or scaling their spacing with **S** in Edit changes coordinates.
The original input file changes only when you explicitly save or export to it.

## Selection identities

An atom's **element** describes its chemistry. Its **label** groups it for
appearance and selection. For example, two groups labelled `O_1` and `O_2` are
both oxygen but can have different colors or bond rules.

In View, you can select and measure a displayed periodic copy at its visible
position. In Edit, copies refer to their underlying atom, so editing one also
changes its periodic images. [Selection](selection.md).

## History boundary

**Command/Ctrl+Z** undoes a committed edit or appearance change;
**Command/Ctrl+Shift+Z** redoes it. Camera orbit, pan and zoom do not enter this
history. **Esc** cancels an unfinished transform.

During atom/molecule placement, **Cancel** removes the current placement session;
**Finish** keeps it. Individual placement batches remain undoable while working.
[Adding atoms and molecules](build-atoms.md).

## Project restoration

Projects with older saved View label overrides restore those labels to their
applicable trajectory frames. A saved substrate label follows its atom while
editing coordinates, switching modes, and stepping between compatible frames.

Opening a project restores its saved structure and presentation. Adding its
frames to an existing trajectory keeps the receiving document's visual settings.
Closing an unsaved document offers **Save**, **Discard** or **Cancel**.

In the desktop app, closing the last tab closes its window, and closing the last
window exits the app. A browser workspace keeps an empty tab instead.
[Opening files](data-input.md) · [Saving projects](save-projects.md).

## Agent-created tabs in a controlled browser

Creating a document through the agent API waits for its editor to become ready.
In one extension-controlled Chrome profile, the new child stayed at
`about:blank` and reported a readiness timeout even though its HTML request
succeeded. The same external command worked in a clean Chrome profile and the
in-app browser. If this occurs, return to the last ready tab, use the visible
**+** button, then query readiness and the active document ID before resuming
agent control. Keep existing documents; do not repeatedly create empty tabs or
change browser security settings. The visible New control remains available.

Command/Ctrl+F opens command search across all workspaces. Escape returns to
the actual search opener.
