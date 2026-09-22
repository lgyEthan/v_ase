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

With two, three, or four ordered atoms selected, **Analyze → Measure** shows
distance, angle, or torsion information. A selected supercell replica retains
its displayed Cartesian position for direct measurement while also exposing
periodic distance information when applicable.

## 3. Inspect the document

The right workbench is divided by purpose, with the atomic viewport always
available at desktop sizes:

| Workspace | Use it for |
| --- | --- |
| Style | Atoms, bonds, cell/supercell and contextual object properties |
| Build | Add atoms/molecules, transform, cell transformation, constraints, relaxation |
| Analyze | Inspect/measure, distributions, motion, fields, interfaces |
| Render | Renderer and output media; project Save is in File and defaults in View |

**Analyze → Measure** shows atom details and deliberate measurements;
selecting an atom does not switch away from a task. Use the header search to
find a control. File/Edit/View/Help menus sit above the canvas; the optional
Objects drawer opens scene objects and their real properties. Select, Move, Orbit, Rotate, Scale, Measure and Add atoms are visible below the
viewport. At narrow widths
the right workbench stacks below the viewport.
On short windows, an open analysis result uses the work area; **Back to
viewport** returns to the structure.

## 4. Play a trajectory

If the file has more than one frame, use the bottom timeline:

- `Space` toggles playback.
- Option+Left/Right Arrow on macOS (Alt+Left/Right on Windows/Linux) moves one frame.
- Plain arrow keys orbit or tilt the structure view.
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
`Esc` cancels an active transform or closes a modal. Click the canvas to return
keyboard focus before using G/R/S when editing a form.
:::

## 6. Undo and redo

`Ctrl+Z` and `Ctrl+Shift+Z` traverse committed user actions in chronological
order. Structure and visual-setting actions share the history. Camera orbit,
pan, zoom, axis alignment, and toolbar navigation are intentionally excluded.

## 7. Save the work

Open **Render → Project save**:

- Save `.vase` for the smallest editable project.
- Enable **Include interactive rendered view** to create one self-contained
  project HTML containing the validated `.vase` archive, poster, and offline
  interactive view.

Use **HTML View** instead when the recipient only needs a lightweight,
view-only 3D handoff. Use the structure export controls when only the current
ASE geometry is needed.

Later use **File → Save** or `Ctrl+S` to reuse the same approved project target
and format. **Save As** chooses a new file. If the browser only downloads a
copy, v_ase does not claim it overwrote the original.

## 8. Close cleanly

Use the tab close control or **File → Close tab**. A dirty tab offers Save,
Discard and Cancel; closing the last internal tab first creates a blank tab so
the workspace and its blocking Python host remain open. Closing the browser
workspace itself ends the connected blocking session. `--no-block` and Python
`block=False` return control earlier and require explicit lifecycle handling.

## A reproducible practice file

From a source checkout, the examples provide small test scenes:

```bash
python examples/basic.py
python examples/constrained.py
python examples/relax.py
```

Continue with [Workspace model](workspace.md) for documents and modes, or jump
to a task in the user guide.
