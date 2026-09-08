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

```{vase-animation} assets/readme_html_quicklook.gif
:alt: A self-contained HTML document in Quick Look and an offline browser.
:fallback: assets/steps/html-preview.png

A self-contained HTML document in Quick Look and an offline browser.
```


## Save Project

**Export > Save Project** has two complete-project outputs.

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

Image and video progress is monotonic across render, capture, upload, encode,
download, and final write. Completion reaches 100% only after the destination
is finished.
