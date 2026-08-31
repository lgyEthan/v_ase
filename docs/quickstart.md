# First session

This walkthrough opens a structure, inspects it without changing scientific
data, makes an optional edit, and saves a complete project.

## 1. Open a structure

```bash
v_ase gui POSCAR
```

Files open in **View** mode by default. View mode avoids attaching the fallback
calculator and keeps large trajectory access lazy when the input format allows
it. Use `--interactive` to start a file in **Edit**:

```bash
v_ase gui POSCAR --interactive
```

The complete local URL is printed before a blocking command waits. Keep the
terminal open while using the document.

## 2. Navigate and select

- Middle-drag to orbit.
- Shift + middle-drag to pan.
- Use the wheel or trackpad to zoom.
- Left-click an atom to replace the selection.
- Shift-click or Shift-box to invert membership in the current selection.
- Use `Ctrl+A` to select all visible atoms.
- Press `X`, `Y`, or `Z` outside a transform to align the camera.

With two, three, or four ordered atoms selected, the Inspect/Measure view shows
distance, angle, or torsion information. A selected supercell replica retains
its displayed Cartesian position for direct measurement while also exposing
periodic distance information when applicable.

## 3. Inspect the document

The control panel is divided by purpose:

| Workspace | Use it for |
| --- | --- |
| Inspect | Selection summary, atom properties, ordered measurements |
| Structure | Cell, replication, labels, atom appearance, bonds, constraints, relaxation |
| Analysis | Displacement, RDF/pair distributions, registry, volumetric data |
| View | Camera, projection, viewport rendering, lighting, background, theme |
| Export | Render Area, images, video, projects, structures, settings, 3D scenes |

Each long panel has a section menu in its header. Select a section to open and
scroll to it; normal scrolling updates the active section label.

## 4. Play a trajectory

If the file has more than one frame, use the bottom timeline:

- `Space` toggles playback.
- Left/Right Arrow moves one frame.
- FPS controls playback speed.
- Skip advances by more than one source frame.

The source trajectory and a generated relaxation trajectory may coexist. Use
the timeline selector explicitly; only the active timeline receives keyboard
playback commands.

## 5. Make an edit

Switch the top-bar mode to **Edit**, select one or more atoms, and press `Esc`
to return keyboard focus to the viewport. Then:

1. Press `G` to move, `R` to rotate, or `S` to physically scale spacing.
2. Optionally press `X`, `Y`, or `Z` to lock a global Cartesian axis.
3. Type an exact value, or move the pointer for an interactive preview.
4. Confirm with `Enter`/left-click, or cancel with `Esc`/right-click.

Constraints are enforced by ASE when **Apply constraints** is enabled. The
browser preview can move freely, but committed coordinates return from the
backend's constraint-aware update.

:::{tip}
`Esc` closes an open panel without clearing the atom selection. This is the
fastest way to restore viewport keyboard shortcuts before a transform.
:::

## 6. Undo and redo

`Ctrl+Z` and `Ctrl+Shift+Z` traverse committed user actions in chronological
order. Structure and visual-setting actions share the history. Camera orbit,
pan, zoom, axis alignment, and toolbar navigation are intentionally excluded.

## 7. Save the work

Open **Export > Save Project**:

- Save `.vase` for the smallest editable project.
- Enable **Include interactive rendered view** to create one self-contained
  project HTML containing the validated `.vase` archive, poster, and offline
  interactive view.

Use **HTML View** instead when the recipient only needs a lightweight,
view-only 3D handoff. Use the structure export controls when only the current
ASE geometry is needed.

## 8. Close cleanly

Close the v_ase document or window. When the final connected page closes, the
default blocking terminal session is finalized and the local server is
released. `--no-block` and Python `block=False` return control earlier and
therefore require explicit lifecycle handling.

## A reproducible practice file

From a source checkout, the examples provide small test scenes:

```bash
python examples/basic.py
python examples/constrained.py
python examples/relax.py
```

Continue with [Workspace model](workspace.md) for documents and modes, or jump
to a task in the user guide.
