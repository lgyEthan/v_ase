# What is new

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
