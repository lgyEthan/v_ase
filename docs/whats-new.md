# What is new

## 0.4.13

- Cartesian axis lines remain visible across the canvas in orthographic views
  along skewed unit-cell vectors. The depth range no longer cuts off the Z axis
  behind the camera. This applies to 3D, flat 2D and image output.
- Camera direction, framing and saved camera settings are preserved. Atoms still
  correctly obscure axis lines behind them; hidden axes remain hidden.

## 0.4.12

- Switch document tabs reliably with the mouse, Command+Option+Left/Right
  on Mac or Ctrl+Alt+Left/Right on Windows. Command/Ctrl+1–8 selects a numbered
  tab; Command/Ctrl+9 selects the last tab. Alt/Option+Left/Right still steps
  trajectory frames. Desktop windows own the tab commands.
- Unit-cell A/B/C views keep a clean Cartesian screen-up orientation instead
  of inheriting roll from other skewed lattice vectors. The view direction and
  repeated-key reversal still follow the actual selected cell vector.
- Build → Rigid translation starts with ordinary coordinate translation:
  Cartesian Å or fractional a/b/c, all or selected atoms, current or all frames.
  No optimizer runs; optional constrained translation and relaxation stay below.
  Transform cell links directly to these controls.
- Deleting atoms from a trajectory in Edit asks whether to delete only in the
  current frame or remove the same zero-based indices in every frame. Shorter
  frames skip missing indices, even when elements differ. Cancel changes
  nothing, and Undo/Redo covers the entire chosen scope.
- Tab activation returns keyboard focus to the canvas. Structural Undo/Redo
  also works after clicking a control; text fields retain native text undo.

## 0.4.11

- Open several files together in one window: choose separate tabs or combine
  all frames into a new trajectory, with a visible, editable file order.
  Works from Finder/Explorer, File → Open and drag-and-drop. Failed or cancelled
  imports preserve existing documents and remove temporary imports.
- Supported structure formats, including `.vasp`, `.cif`, `.xyz` and `.extxyz`,
  appear as macOS Open With candidates. Only `.vase` claims format ownership;
  other file types retain the user's existing default app.
- **A / B / C** looks along the actual unit-cell vectors; press the same key
  again for the opposite side. **X / Y / Z** remains Cartesian. Whole-structure
  selection uses **Command/Ctrl+A**. Missing cell vectors disable their shortcut.
- Flat 2D bonds have uniform unlit colors and sharp side outlines, with no
  blurred shading or black seam where their two atom colors meet. The same
  appearance is used in images, movies and standalone HTML.
- Stored force-vector displays refresh after physical edits, preventing a stale
  layer from blocking subsequent frame changes. Displacements with no comparison
  frame no longer leave image rendering waiting for unavailable data.

## 0.4.10

- FixedPlane constraints use planetary rings with a translucent cyan face and
  distinct darker edges. Selecting an atom expands its ring around the yellow
  selection outline while preserving the width of the face.
- Selection and hover reveal the blocked normal as a dashed line with X ends.
  Rings, atoms and selection outlines respect their actual 3D depth in both
  3D and flat 2D; no large plane hides the surrounding structure.
- Constraint marks follow live positions and property-based atom radii,
  including trajectory interpolation. Zero-radius atoms hide their marks.
- Images, movies and standalone HTML share the same constraint rendering.
  Publication exports use the nonselected ring when selection is hidden.
- The Orbit tool rotates the view with a primary-button drag; Shift-drag pans.
- AI tool schemas correctly describe the global Z axis for commensurate rotation.
  Explicit guest indices stay selected so later styling and camera fitting preserve
  the common-cell preview.
- Rigid translation relaxation reports completion as one consistent state,
  including very short optimizations.


## 0.4.9

- Atom selection and constraint marks remain visible in both 2D and 3D.
- Add Atoms/Molecules is easier to use on Windows and at larger display scales,
  with one vertical scroll area and reachable placement controls.
- Optional relaxation stays with the placement controls: place, relax if needed,
  then Finish or Cancel.
- **Clear Relaxation Trajectory → Restore Starting Structure** returns to the
  beginning of that relaxation run, including atoms you just placed.
- Blender export includes editable water surfaces and trajectory animation.
- Placement guides stay out of exported figures and disappear after Finish.
  Isosurfaces and water surfaces update correctly when their visibility or
  source data changes.

## 0.4.8

- Render detected H₂O as a continuous water envelope in the canvas, trajectories,
  images, movies/GIF and offline HTML. Keep solids and ions atomistic.
- Use molecular-scale water defaults, numeric atom/bond detail and independent
  surface subdivision/smoothing with progress, cancellation and recovery.
- Find stored Forces and Isosurfaces in Style; keep surface definitions separate
  from renderer mesh finishing.

- Keep selection, hover properties and transform readouts from changing canvas
  height; redraw resized canvases before a blank frame can appear.
- Use matching camera visibility icons in the viewport, Renderer and Objects.
  The camera stays fixed in space by default; **Lock camera to viewport** is an
  optional toggle that switches off when the camera is hidden.
- Fit camera view beside the right panel. Show rotation arrows inline when they
  fit, or use a smoothly expanding chevron on narrower canvases.

## 0.4.7

- Preserve atom magnification, render composition and Undo history when detaching
  into a smaller window. Camera scale Undo/Redo also survives viewport resizing.

- Make Selected atoms appearance live: separate labels on commit or create the
  next unused element suffix on color/material/opacity/size edits. Synchronize
  actual radius and every appearance field with the per-label table; remove the
  redundant Surface material section and Apply action. Undo the initial split
  and first gesture together. Confirm existing-label merges and inherit their
  complete style without changing unselected members or chemical elements.
- Clarify **Lock camera to: World / Viewport** and keep the camera-view indicator
  with axis views, separate from **Align camera to current view**. Looking through
  a camera preserves its lock. Viewport-locked camera G/R/S keeps the render area
  stationary; X/Y/Z updates it immediately. Preserve saved camera values through
  passive resizing and project restoration. Start new scenes centered in the
  usable space beside the inspector without moving saved or user-adjusted views.
- Use **Render area** consistently. Add an oriented angle arc to the wire camera
  and an explicit selectable Camera badge that remains reachable when the area
  extends outside the viewport. PNG and video/GIF share its stored composition.
- Share Objects visibility with rendering; add Constraints visibility independently
  of ASE enforcement. Draw crisp 2D fixed-atom crosses and disable irrelevant
  material/lighting controls in flat mode, including export dialogs.
- Move single-atom label, XYZ, stored properties and forces into the footer;
  remove the floating note and element/mass/fractional-coordinate boilerplate.
  Select the first Supercell value when its shortcut opens the controls.
- Show nonblocking activity for scalar catalogs, color/radius mapping, analysis
  and volumetric rendering. Load stored force vectors when enabling them through
  a scene preset and wait for their current-frame rendering before reporting
  scene readiness. Preserve committed export guide choices in Objects.
  Preserve per-frame chemistry and unedited labels
  when switching View/Edit on trajectories with changing elements. Keep Undo
  clean when default label materials need no explicit override.

## 0.4.5

- Reopen `.vase` immediately in its saved Edit/View mode, source frame,
  camera, appearance, selection and inspector presentation. Use a new tab
  when another document has content; remove redundant project import prompts.
- Separate **Navigate: Scene / Camera**, **Look through camera** and **Align
  camera to view**. Switching the navigation target preserves the output
  composition. Add camera G/R/S with cancellable previews and saved scale.
- Replace the floating eye marker with an oriented wire camera and output
  plane. Keep atoms visible through orbit and close camera positions with
  geometry-aware drawing limits; replace finite grid tiles with an adaptive
  analytic work plane that cannot occlude atoms.
- Expose 2D/3D atom style in Renderer as well as Viewport. Keep export profiles
  through appearance edits and exclude viewport guides consistently in every
  captured animation frame.
- Preserve selection and measurement intent across animation export without
  reporting internal capture frames as human edits. Allow empty selected
  colorscale targets through native commands and trajectory export.
- Wait for already-publishing collaboration events before returning a revision
  barrier, preventing delayed notifications from invalidating a fresh guard.
- Limit automatic desktop file handling to `.vase`. Remove JSON and generic
  suffix registrations; retain explicit scientific-format opening without
  replacing another application's defaults. Clean only v_ase's obsolete
  Windows Open With registrations during upgrade.
- Make desktop Command/Ctrl+W close the last document's window and quit after
  the last window, including an empty window. Preserve save/cancel guards and
  other windows; browser documents retain their internal blank-tab behavior.

## 0.4.4

- Clarify colorscale targets with **Selected atoms**, an explicit **Use current
  selection** button, and label choices that capture base indices. Preserve
  manual bounds and the chosen range mode when changing targets.
- Retain color and radius targets through trajectories with changing atom
  counts and elements, including saved projects at a shorter frame. Missing
  indices resume their mapping when they return. Match these targets in HTML.
- Preload scalar metadata and retain dropdown options for faster property
  selection. Show all stored single-atom properties, including custom arrays
  such as existence, in the scrollable bottom readout.
- Put the output guide and camera controls inside **Output frame & scale**,
  separate from Lighting, Quality, and Overlays & background.
- Add **Camera to view** and **View camera**. A fixed physical output camera
  stays independent of editing orbit, axis views, pan and zoom; looking through
  it fits the whole output frame. Follow mode continues to track editing views.
- Use the same saved camera for PNG and default video/GIF output. Report the
  effective camera in video metadata and verify GIF framing against PNG output.
- Let settings navigation recover from invalid drafts without applying them,
  preserving Command/Ctrl+Shift+P and Command/Ctrl+Shift+A. Save and explicit
  commits continue to reject invalid scientific values.

## 0.4.3

- Distinguish the castle application icon from paper-shaped VASE/ATOM document
  icons. Register readable structures as Open With candidates on Mac/Windows;
  only `.vase` is the native default type, preserving other application defaults.
- Reorganize Atoms into explicit scope sections, restore compact one-row-per-label
  tables with horizontal scrolling, and clarify property, range and mapping targets.
- Freeze selected colorscale targets until explicit reapplication; preserve them
  across compatible frames and known deletion/duplication/replication operations.
- Commit trajectory coordinates, colors and radii together, coalesce frame loads,
  retain bounded property caches and discard superseded requests without errors.
- Invalidate pre-edit trajectory position caches so frame roundtrips and video
  export preserve committed physical edits, including late cache responses.
- Pin table headers directly against their top border, without inset gaps or
  rows showing above them; bound long label/bond tables with local scrolling.
- Replace the rendered inset with a crop guide on the editable canvas. Preserve
  viewport picking and stable composition when the floating inspector changes.
- Fix output framebuffer resizing during Retina video capture; add inclusive
  source-frame ranges and animated GIF with loop-forever/play-once control.
  Interpolate raw continuous colorscale and radius values for animation samples.
- Simplify first-open dialogs in empty workspaces and complete selection drags
  reliably across the floating inspector.

## 0.4.2

- Replace repeated workbench symbols with 23 distinct section icons, hover/focus
  names, and section headings below the bookmark strip. Group the left toolbar
  by selection/measurement, selected-object transforms, camera and creation.
- Make Move/Rotate/Scale wait for an editable selection and a viewport drag;
  preserve modal G/R/S, explicit Apply/Cancel and exclusive tool state. Wait
  for pending physical edits before Undo/Redo.
- Float the right panel over a stable canvas and widen it up to 900 px. Normalize
  option typography, align selection controls, and keep fields and units inside
  their bounds. Restore the canonical GitHub logo in the editor header.
- Default Bonds to editable pair specifications; remove the redundant Automatic
  radii selector and retain suggested-cutoff reset and explicit index pairs.
  Preserve guest-label bonds in cell-match previews.
- Support Ctrl+A for entire numeric fields even on Mac, consecutive cutoff
  editing with Tab/Shift+Tab, and Open with Command+O / Ctrl+O. Make menus
  switch on hover, coordinate with search, and expose a visible Reset menu.
- Open dropped projects/structures in the current trajectory, a new tab or a
  new window. Desktop tabs detach into independent windows, preserving their
  scientific session, camera, undo history and original writable save target.
  Closing one window releases only its workspace; Quit checks every window.
- Replace the desktop icon with the full atomic-bead castle, keeping its small
  Pinocchio detail and removing the projecting red foundation board. Retain Python/Jupyter support.
- Apply saved per-atom colorscales during initial project loading, so a fresh
  launch is ready to render without toggling its scalar settings.
- Remove the decorative HTML orbit GIF, recapture scientific examples and
  synchronize user documentation and the canonical agent workflow.

```bash
python -m pip install --upgrade "v_ase-gui[mcp]==0.4.2"
```

See the [desktop installation guide](desktop.md) for Mac/Windows downloads,
window management and file associations. Restart running GUI/MCP servers
when upgrading.

## 0.4.1 — redesigned scientific workspace

This release introduces a wide viewport, an optional Objects drawer,
a single Style/Build/Analyze/Render workbench with responsive stacking,
exact editor shortcuts, explicit Measure mode, property-based atom radius,
independent output px/Å, and retained project Save/Save As with safe document
closure. Mac commands use Command, while Windows/Linux use Ctrl; fullscreen
Keyboard Lock is offered with explicit support/denial feedback rather than a
universal interception promise. Child-tab reloads now preserve both unsaved
commits and clean saved appearance. The new [workspace](workspace.md), [radius](property-radius.md),
[rendering](render-images.md), and [project](save-projects.md) guides describe
these workflows. Scientific tools are visible in each workbench, while
contextual object settings and analysis results stay beside the structure.

```bash
python -m pip install --upgrade "v_ase-gui[mcp]==0.4.1"
```

Restart running GUI/MCP servers after upgrading. Existing tunnel IDs and keys remain
usable; refresh the ChatGPT connection's discovered tools if needed.


## 0.3.8

**Rendering menu fix.** Render Lighting controls remain clickable outside the scrolling toolbar.

[Lighting controls](render-images.md#render-lighting) · [MCP tools](ai-tools-reference.md) ·
[Complete changelog](https://github.com/lgyEthan/v_ase/blob/main/CHANGELOG.md)
