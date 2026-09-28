# Water surface — experimental branch

Open **Style → Water**, enable **Show water surface**, then adjust color,
opacity and **Lighting & reflections**. **Replace molecular spheres** hides only
the water molecules participating in the visible envelope; disable it to inspect
both representations. Ions, membrane atoms and other species stay atomistic.
**Objects → Water surface** controls the same layer.

This experiment belongs to `codex/water-surface`; it is not in the published
0.4.7 app. The original checkout and `main` remain separate.

## What the surface means

Water is detected from chemical elements, independently of visual labels and bond
settings: each hydrogen belongs to the nearest oxygen inside the O–H cutoff
(default 1.25 Å), and oxygen with exactly two assigned hydrogens qualifies.
Periodic neighbours are considered. This is a geometric heuristic, not a reactive
chemical species classifier. Hydronium, hydroxide, coarse-grained water and
heavily dissociated structures need a different model and are not classified as H₂O.

The displayed surface is an isosurface of a sum of Gaussian oxygen-centred
kernels. **Smoothing** is the kernel width in Å; **Density threshold** is a
relative scalar threshold, not a calibrated density in g/cm³. Lower thresholds
expand the envelope. Large smoothing can connect nearby regions across a narrow
membrane or gap: inspect the molecular representation and adjust it. The envelope
does not infer a physical liquid boundary, fill the simulation box automatically,
or solve fluid dynamics. No artificial time-dependent waves are added.

**Selected water oxygens → Use current selection** captures base oxygen indices.
Later selection changes do not redirect the layer. Missing indices are retained
across trajectory frames. Only currently detected H₂O in the scope is drawn.
The same-index correspondence is visual, not a claim of chemical identity during
reactive simulations.

## Playback and output

The surface is regenerated from the coordinates actually drawn, including
interpolated trajectory/movie samples. A coalesced build at the draw boundary
keeps the atoms and their water envelope in one render. Changing only camera pose
reuses geometry. Color/opacity/lighting changes do not rebuild the density grid.

Image and movie/GIF captures use the same surface and Render Area as the viewer.
`.vase` stores water settings; self-contained HTML embeds the local geometry and
renderer modules and works offline. There are no new Python dependencies.
In flat display mode the surface is unlit; saved lighting preferences remain.

The current envelope is available in canvas/PNG/video/GIF/HTML. **Blender, OBJ and
Rhino geometry exports do not yet include this experimental layer.** Those formats
are explicitly rejected while the layer is enabled, so they cannot silently
omit the water. Disable the surface deliberately to export molecular geometry.

## Performance and bounds

The experimental implementation uses CPU density reconstruction with GPU surface
rendering. It does not promise 60 fps for arbitrary datasets. Preview grid spacing
can adapt to stay within 300,000 samples, 128 samples per axis and a bounded kernel
work budget; the status line reports the effective spacing. At most 20,000
molecules including displayed repetitions and 200,000 triangles are accepted.
Requests that cannot preserve a resolved envelope fail visibly and restore the
molecular representation. These are allocation guards, not recommended workloads.

For dense or long trajectories, increase grid spacing or restrict the source.
The world-anchored lattice avoids moving the whole sampling grid with each molecule.
Periodic molecular detection and displayed supercells are supported; the outer
surface is the envelope of the displayed molecules, not a cell-clipped periodic
continuum. Strongly skew/unreduced cells require further neighbour-image testing.

## Reproducible example

```sh
python examples/water_surface.py
```

This creates 24 synthetic frames containing 150 water molecules, a perforated
carbon-like sheet and ions. It is an illustration of rendering behavior, **not an
MD trajectory, membrane permeability calculation or desalination result**. It
requires no proprietary reference image or video assets.

![Synthetic water envelope around a perforated membrane](assets/water-surface-experiment.gif)

The GIF above was exported by the application: 24 frames, 960 × 640 pixels,
15 px/Å, infinite loop. It uses the same rendered water layer as live playback.
The light effects use surface shading and environment reflections; this prototype
does not implement physically accurate refraction through the fluid.

## Validation and next integration gate

Evidence collected on 28 September 2026 in this isolated worktree:

- Full regression run: 1,103 passed / 5 failed out of 1,108. The failures exposed
  a missing guide registration, an oversized discovery schema, missing water
  imports in the documentation runtime, and the old bookmark count. The MCP
  subprocess check also saw different schema revisions while that run was in
  progress. All five now pass; the complete affected skill/MCP/docs/editor test
  modules passed together (**61 passed**). The entire suite was not rerun after
  those focused fixes.
- Water-specific unit/browser tests: **6 passed**, including reversible visual
  history, captured selection scope, exact project-coordinate preservation,
  changing rendered positions, exact capture dimensions and standalone offline
  HTML. Offline assertions use the DOM without relaxing its content security policy.
- Earlier combined HTML, video, project-consistency, typed-AI and water checks:
  **64 passed**. These overlap the full run and are not additional unique tests.
- Strict Sphinx HTML build, wheel/sdist build and `twine check` passed. These are
  local experimental artifacts, not a published version or a desktop installer.
- The in-app browser visibly rendered the example and played its trajectory.
  A local Chromium sample of 12 frames reported roughly 22 ms average surface
  refresh (one sample reused cached geometry); this is not a general frame-rate
  guarantee. The exported GIF above was inspected visually.


Run `tests/test_water_surface.py`, `tests/test_browser_water_surface.py`, existing
HTML/video export tests, project consistency and typed AI schema tests. Check real
playback, exact exported dimensions, scientific coordinate immutability,
visibility on/off, custom labels, periodic water, captured scopes, malformed data,
no-water frames, document switches and undo. Inspect the resulting image/movie.

Before a main/release integration: benchmark larger real aqueous trajectories,
complete geometry-export parity, test unusual periodic cells and reactive water
labels, decide whether worker/GPU reconstruction is needed for the supported
workloads, and execute the full release checklist with refreshed examples. Do not
publish this experiment as a validated fluid solver.
