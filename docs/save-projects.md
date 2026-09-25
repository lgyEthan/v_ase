# Save projects and share HTML

Keep a fully restorable document, or share an offline interactive view.
Use **Save Project** for continued editing and **HTML View** for a lightweight
viewing copy. A structure file alone does not retain the complete figure setup.

## Example: send an interactive surface figure

1. Open and style the [Cu surface example](appearance.md).
2. Choose **Save Project** and save `.vase` to preserve the working document.
3. For a single file with both viewing and restoration, enable **Include
   interactive rendered view**. The output changes to `.html`.
4. Open the HTML in a browser without the local Python server; orbit and zoom.
5. Reopen the project in v_ase and check labels, camera, constraints and fields.




## Save Project

**File → Project save settings** has two complete-project outputs.

### Compact `.vase`

The default is the smallest editable source of truth. It stores:

- structure or trajectory frames, cell, PBC, labels, arrays, and constraints;
- safe stored calculator results;
- current frame and compatible analysis state;
- camera, appearance, bonds, lighting, display, and Render Area settings;
- validated volumetric datasets and their display definitions.

The archive is self-contained and does not reference the original input file.
Volumetric arrays use validated compressed members; project loading does not
execute an arbitrary pickle payload.
Save waits for pending scientific edits and frame work, and refuses an invalid
active scientific field before opening a file picker. Closing or replacing a
document waits for pending edits before offering Save, Discard or Cancel; a
failed physical apply keeps the document open with an error. Field import,
combination and removal all count as unsaved scientific changes, even when
the affected field is not currently displayed.

The current source also stores per-frame cell origins in the `.vase` manifest.
ASE `.traj` alone does not preserve `celldisp`; use `.vase` or project HTML when
the displaced cell guide must reopen exactly. Older projects without this
optional field retain a zero origin.

### Project HTML

Enable **Include interactive rendered view** to change the output to `.html`.
It embeds the complete `.vase` recovery data plus an offline interactive 3D
viewer and optimized poster. The same file can be inspected without Python and
later reopened in v_ase:

```bash
v_ase gui project.html
```

The HTML is larger than `.vase` because it contains renderer assets, scene
data, poster pixels, and a Base64 project archive.
Renderer Undo/Redo restores the editable HTML project's own saved output
profile as well as the visible controls. An internal-tab reload retains the
project's original format, output profile and available writable target;
Save As updates that retained target only after a successful write. An unsaved
visual edit in the child stays visible and dirty after the child reloads. A
successfully saved appearance is restored on reload even though its tab is
clean; repeated edits while dirty retain the latest committed value.

## HTML View

**HTML View** is the share-oriented alternative. It creates a self-contained
offline, view-only document that supports orbit, pan, zoom, and trajectory
playback but exposes no scientific editing controls.

Project embedding is off by default, producing the lightest handoff. Enable
the embed option only when the same file must also recover the editable project.
A lightweight HTML without embedded recovery data cannot be opened as an
editable v_ase document, and v_ase reports that distinction explicitly.

The poster and live WebGL canvas use the same Render Area rectangle. Finder/
Quick Look can display the poster without executing WebGL; in a browser the
live scene replaces it after the first prepared frame.

## Visual settings preset

Export/Import Preset moves structure-independent presentation settings between
documents or computers. It excludes coordinates, trajectory frames, cell
contents, and absolute per-atom data. A personal visual default automatically
applies compatible settings to new structures and tabs on the same user
account/computer.

Use `.vase` when scientific document state must be exact; use a preset when
only a reusable house style is intended.

## Save lifecycle and progress

Where the browser File System Access API is available, v_ase opens the native
destination picker before expensive rendering or scene generation. Canceling
the picker cancels the operation. Chrome may show its own permission notice for
the selected destination; v_ase receives write access only to that user-chosen
file.

After a successful project save, **Save** reuses that approved writable target
and original `.vase` or project-HTML format. **Save As** chooses a new target;
the old file is unchanged until the new write succeeds. An HTML project retains
its output profile when saved again. The File menu, quick Save button and
`⌘S` on macOS or `Ctrl+S` on Windows/Linux uses that retained target; **File → Project save settings** opens the format
dialog explicitly. A browser without a reusable file handle
downloads a new copy and says so explicitly. An uploaded raw structure or
temporary source path is never treated as an implicit overwrite target.

When a `.vase` or editable HTML project was explicitly opened from the terminal
launch-directory picker or as a CLI/Python project path, the local server may
save back to that exact opened file. The path is kept private to the session;
the browser receives only an opaque binding. v_ase verifies the original file
has not changed externally, writes a staged file beside it and atomically
replaces it. An external edit yields a conflict instead of being overwritten;
the tab marks the save error and offers Retry Save or Save As. Reload only if
you intend to discard the current in-memory edits. The same best-effort
size/modified-time check applies
to retained browser file handles. v_ase checks such a handle again after
serialization or poster rendering and immediately before opening the writer;
browser handles do not provide an atomic compare-and-swap against an external
writer racing after that final check.

An editable HTML project reopens as HTML, including its saved render profile;
this remains true when it opens in a new internal tab. If the browser supplied
a writable handle, that tab retains it; otherwise Save downloads an HTML copy
rather than converting to `.vase`.
an ordinary `.vase` extracted from HTML remains `.vase`. One-off HTML/image/
video exports do not change the project's format or writable destination.

Document tabs show changed and saving state. Closing a changed tab offers
Save, Discard or Cancel; canceling a destination picker leaves the tab open.
Replacing a dirty tab uses the same choice. Closing or reloading the browser
page requests the browser's supported unsaved-changes confirmation; canceling
that exit leaves the live session intact. Save waits for pending physical
application and playback/frame work before taking the project snapshot.
In the browser, closing the last tab creates a new blank document. In the desktop
app, Command/Ctrl+W on the last tab closes its window; the last window exits the
app. The same Save/Discard/Cancel guard applies.

Image and video progress is monotonic across render, capture, upload, encode,
download, and final write. Completion reaches 100% only after the destination
is finished.

## Reopening the saved workspace

Open a `.vase` file directly: no reader or Edit/View prompt appears. Its saved
mode, active trajectory frame, camera, appearance, render-area visibility,
selection and properties-panel location are restored. The first project uses
an empty startup tab; another project opens in a new tab and preserves the
current document. Older archives restore the fields they contain and default
to Edit only when no mode was stored. Different window sizes retain physical
view magnification while adapting the available UI area.

## Render area and visible objects

**Render → Renderer → Render area & scale** owns dimensions, physical px/Å,
and **Show render area**. **Lock camera to → World** fixes its physical pose;
**Viewport** keeps its frame on screen while navigation adjusts the composition.
The camera-view icon beside the axis views returns to the camera without changing
that lock. Orbiting in World mode deactivates the icon; zoom and pan do not.
**Align camera to current view** deliberately changes the output camera.

Select the **Camera** badge or the outlined camera wedge/plane, then G/R/S to
translate, rotate or scale the render area. The editable scene remains live.
In Viewport lock, the frame stays still while atoms, cell and the surrounding
scene move together. PNG and animation capture use the same stored render camera.
**Objects** visibility also applies to rendering, including grid, axes, cell,
bonds and constraints. Hiding Constraints changes only drawing; ASE constraints
remain stored and enforced. Renderer overlay controls mirror those same choices.
Saving a GUI image/video export synchronizes its guide choices with Objects.
Enable a hidden guide in Objects first; export settings cannot reveal it alone.
