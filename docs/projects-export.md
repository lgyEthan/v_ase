# Projects, rendering, and export

v_ase separates the editable scientific project, lightweight offline sharing,
rendered media, and reusable geometry exports. Choose the output based on what
the recipient must recover.

## Render Area

Image, video, and HTML use one persistent **Render Area**. Its visible boundary
and gray outside mask define the exact saved composition.

- **Follow viewport** keeps the export camera synchronized while you orbit,
  pan, zoom, and align the working view.
- Disable it and choose **Set from Current View** to lock a composition while
  continuing to inspect or edit in the main viewport.
- In Edit, the Render Area eye can be selected and moved with `G`, translating
  its camera and target together.

The Render Area owns aspect ratio, dimensions, projection/camera, overlay
choices, quality, and crop. Picking inside it uses the same camera, so pointer
selection remains aligned with visible atoms.

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

## Structure and data output

| Output | Contents and intended use |
| --- | --- |
| POSCAR | Current physical ASE structure in VASP format |
| ASE Pickle | Current `Atoms`, labels, constraints, arrays, and safe stored calculator results |
| RDF CSV | Radius, total `g(r)`, and requested partial curves |
| Commensurate CSV | Candidate angles/matrices, area ratios, residual strain, search metadata |
| Registry CSV | Complete translation grid, plane basis, Cartesian vectors, metric values |

The CLI `-o/--output` path writes the finalized physical structure through ASE;
`--output-format` overrides ambiguous output detection.

## Image output

Images support:

- optimized PNG;
- JPEG;
- lossless WebP; and
- a single-page 300 dpi PDF containing the rendered pixels.

The semantic renderer normalizes width/height to 64–8192 pixels. The chosen
dimensions and Render Area camera determine the exact output; JPEG and PDF are
opaque, while PNG/WebP can retain supported transparency.

Lossless WebP and optimized PNG preserve the requested pixel dimensions and
RGBA result. PNG recompression is used only when it is smaller than the browser
source.

## Video output

Trajectory video supports H.264 MOV and MPEG-4 AVI at a constant requested
frame rate. The browser captures each rendered frame, then the bundled
imageio-ffmpeg runtime transcodes the final portable file.

At interpolation multiplier `1x`, every source frame appears exactly once. For
`N` source frames and multiplier `m`, the output has
`(N - 1) * m + 1` frames. Optional MIC interpolation uses adjacent cells and
shared periodic axes; it never mutates the source trajectory.

The video background is opaque white. Visible analysis overlays are refreshed
for each output frame rather than copied from one source frame.

## 3D scene output

### Blender

The generated Python scene uses grouped/instanced atom geometry, bond styles,
optional cell, trajectory animation, camera, and lighting. Optimized output
avoids one Blender object per atom; select individual-object output only when
atom-by-atom Blender editing is required.

### OBJ/MTL

OBJ export is a static scene packaged with MTL plus camera/metadata sidecar
information. It has no optional Python dependency.

### Rhino 3DM

3DM export uses block-instanced atoms and bonds, metadata, materials, and saved
views. Install the optional dependency first:

```bash
python -m pip install -e ".[symmetry,phonon,rhino]"
```

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

## Automation exports

The semantic interface exposes 13 export kinds: `image`, `video`, `poscar`,
`pickle`, `blender`, `3dm`, `obj`, `html`, `project`, `settings`, `rdf-csv`,
`commensurate-csv`, and `registry-csv`. Always read the live `schema` before
building an automated request; see [AI-agent integration](ai-agents.md).
