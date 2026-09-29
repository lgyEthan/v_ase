# First steps

Open a structure, explore it, make an edit and save your work.
If you do not have an input file, download an [example structure](example-inputs.md).

## 1. Open a structure

In the desktop app, choose **File → Open** (`Command+O` on Mac, `Ctrl+O` on
Windows), or drag a structure into the editor. With Python installed, you can
also open a file from a terminal:

```bash
v_ase gui POSCAR
```

Structure files normally open in **View** mode. A saved `.vase` project reopens
in its saved mode and appearance. [Opening files](data-input.md).

## 2. Move around the structure

- **Middle-drag** to orbit; **Shift + middle-drag** to pan.
- Use the **wheel or trackpad** to zoom.
- Press **X**, **Y** or **Z** to look along an axis.
- Choose **Fit view** if the structure is outside the visible area.

[Complete mouse and keyboard controls](shortcuts.md).

## 3. Select and inspect atoms

Click an atom to inspect it, or drag a box to select several atoms.
**Shift-click** adds or removes an atom. **Command/Ctrl+A** selects all visible
atoms when the cursor is outside an input field.

To measure a distance, angle or torsion, select two, three or four atoms
individually in the intended order. Bulk box selection does not create an
automatic measurement. Open **Analyze → Measure** for measurement controls.

## 4. Choose a task

| Panel | What you can do |
| --- | --- |
| **Style** | Change atoms, bonds, supercells, polyhedra, water surfaces, isosurfaces and force vectors. |
| **Build** | Add atoms or molecules, transform a structure, edit its cell, set constraints and relax. |
| **Analyze** | Measure geometry and explore trajectories, distributions, fields and interfaces. |
| **Render** | Set a camera and export images, animations or 3D scenes. |

Hover over a panel's icons to see the section names, or use the search button
to find a control. **Objects** controls which scene objects are visible.

## 5. Make an edit

Switch the top bar to **Edit**, select the atoms to change, and click the canvas.

1. Press **G** to move, **R** to rotate, or **S** to scale their spacing.
2. Optionally press **X**, **Y** or **Z** to constrain the axis.
3. Move the pointer for a preview, or type an exact value.
4. Press **Enter** to apply or **Esc** to cancel.

Use **Command/Ctrl+Z** to undo. Camera navigation does not fill the undo history.
[Move atoms](move.md) · [Rotate atoms](rotate.md) · [Constraints](constraints.md).

## 6. Play a trajectory

For a file with multiple frames, use the timeline below the canvas.
**Space** starts or pauses playback. **Option/Alt + Left/Right** steps through
frames; **FPS** changes playback speed. [Trajectory controls](trajectories.md).

## 7. Save or share

Choose **File → Save** (`Command/Ctrl+S`) and save a `.vase` project to keep your
structures, camera and appearance. **Save As** makes a separate copy.
Export **HTML View** when someone only needs to explore your result in a browser.
[Saving and sharing](save-projects.md).

Close a document using its tab's **×** or **Command/Ctrl+W**. Unsaved work offers
**Save**, **Discard** or **Cancel**. In the desktop app, closing its last window
exits the app. A browser workspace keeps an empty tab ready for another structure.
