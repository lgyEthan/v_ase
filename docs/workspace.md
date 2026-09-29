# Find your way around

The atomic structure stays in the canvas. Use the top menus for files, the left
toolbar for direct interaction, and the right panel for the current task.

## Workspace and documents

Each tab is a separate document with its own structure, trajectory, selection,
camera, appearance and undo history. Use **+** for a new document or
**File → Open** to load a file. In the desktop app, drag a tab below the tab bar
to move it to its own window.

| Area | Use it for |
| --- | --- |
| **File** | Open, Save, Save As and structure export. |
| Left toolbar | Select and measure atoms; move, rotate or scale a selection; orbit the view. |
| **Objects** | Show or hide atoms, bonds, cell, guides, constraints and camera. |
| **Style** | Atom appearance, bonds, supercells, polyhedra, water, isosurfaces and stored forces. |
| **Build** | Add atoms/molecules, transform, edit the cell, add constraints and relax. |
| **Analyze** | Inspect measurements, trajectories, distributions, fields and interfaces. |
| **Render** | Configure lighting, quality and output; export images, animations and 3D scenes. |

Panel icons are section shortcuts: hover or focus one to see its name.
The header search finds controls across panels. Drag the right panel's edge to
resize it; opening the panel does not move your view of the structure.
On a narrow window the panel sits below the canvas.

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

Opening a project restores its saved structure and presentation. Adding its
frames to an existing trajectory keeps the receiving document's visual settings.
Closing an unsaved document offers **Save**, **Discard** or **Cancel**.

In the desktop app, closing the last tab closes its window, and closing the last
window exits the app. A browser workspace keeps an empty tab instead.
[Opening files](data-input.md) · [Saving projects](save-projects.md).
