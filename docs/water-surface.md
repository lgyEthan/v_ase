# Water surface — experimental branch

Open **Style → Water**, enable **Show water surface**, then adjust color,
opacity and **Lighting & reflections**. **Replace molecular spheres** hides only
the water molecules participating in the visible envelope; disable it to inspect
both representations. Ions, membrane atoms and other species stay atomistic.
**Objects → Water surface** controls the same layer.

This experiment belongs to `codex/water-surface`; it is not in the published
0.4.7 app. The original checkout and `main` remain separate.

## What the surface means

Water uses the source's positive integer molecule IDs (`mol`, `molecule_id`,
`molecule_ids`, `molid` or `mol-id`) when present. A declared group must contain exactly one
O and two H, with both O–H distances inside the chemical cutoff (default 1.25 Å),
including periodic images. It never borrows H from a neighbouring declared
molecule. Groups that are not H₂O stay atomistic. IDs are independent of mutable
visual labels; zero/unassigned IDs fall back to geometric neighbour detection.

Without IDs, each H belongs to its nearest O inside the cutoff; an O with exactly
two assigned H qualifies. This fallback is a geometric heuristic. Hydronium,
hydroxide, coarse-grained water and heavily dissociated structures are not H₂O.

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
keeps the atoms and their water envelope in one render. Stored molecule IDs are
committed with each frame; sources with changing IDs bypass coordinate-only
caches, including while the layer is off. Video interpolation rejects changed IDs
and asks for original source-frame export instead. Changing only camera pose
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

The implementation reconstructs a Gaussian density on the CPU, then creates an
**indexed boundary mesh**: interior grid cells create no geometry, and adjacent
surface faces share vertices. Source molecules inside the liquid contribute to
the density, but their individual sphere and bond instances are removed from the
GPU draw count when **Replace molecular spheres** is on. Bounded scratch arrays
are reused across builds to reduce allocation and garbage collection; each mesh
owns its output buffers, so another frame/document cannot overwrite it. Scientific atom data,
selection identities and coordinates remain available and return when it is off.
This also applies to repeated cells and individually hidden instances.

Orbit, pan, zoom and color/opacity/light changes reuse the completed mesh. New
coordinates, molecular topology, source scope, source visibility, shape settings
or displayed repetitions invalidate it. Trajectory samples must recalculate the
surface; a static view does not. It does not promise a universal frame rate.

The lattice is world-anchored. Grid spacing adapts to bounded allocation/work:
1,200,000 samples, 512 per axis, 120,000,000 estimated kernel samples and up to
500,000 displayed molecules. These are safety limits, not recommended workloads.
Effective spacing and build time are shown explicitly; an unresolved or excessive
request fails visibly and restores molecular spheres. There is no old 200,000
triangle cutoff: index/vertex allocation is bounded by the grid itself.

Repetitions use exactly the renderer's signed cell offsets (for example three
copies are −1, 0, +1). The surface is reconstructed over the combined visible
molecules, including cross-cell neighbours, so internal cell seams are not capped
by duplicating a finished single-cell shell. A hidden base atom does not discard
its visible replicas. The envelope extends around displayed molecules rather
than clipping to the simulation cell faces. Source detection with IDs bounds
periodic images using reciprocal vectors, including the geometric fallback for
unreduced cells. Geometric detection bounds the image search to 4,096 shifts and
2,000,000 oxygen image entries; excessive requests fail with a cell-basis or
molecule-ID remedy rather than silently missing neighbours.

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

Verification on 2026-09-28: **1,114 full-suite tests passed**, plus a final
**13-test water-focused run** including the additional unreduced-cell regression.
The strict Sphinx HTML build, wheel/sdist build and `twine check` passed. The built
wheel was smoke-checked in a temporary environment sharing installed dependencies;
this is not a clean published-release installation test. No release was performed.

The large-system revision checks stored molecule topology, closed indexed meshes
(including dense low-threshold boundaries), real GPU instance counts, cached
camera/material changes, signed repetitions, replica picking, per-instance
visibility, streamed topology changes and recovery after a rejected surface.

On a supplied **52,272-atom snapshot containing 13,560 water molecules**, all
13,560 declared H₂O groups were recognized. The previous nearest-neighbour-only
prototype missed 48 groups. With replacement enabled, 40,680 individual water
atom instances were excluded: only 11,592 non-water atom instances remained.
The entire scene's submitted triangles fell from approximately **13.92 million
to 4.25 million** (69%). This is actual draw-count reduction, not zero-radius
spheres still submitted to the GPU. The surface itself used about 303,000
triangles and 151,000 shared vertices; observed browser builds took roughly
110–125 ms.

A **2 × 1 × 1** displayed supercell produced an envelope from all 27,120 visible
water molecules. Both base and replicated water sphere instances were omitted;
non-water atoms and replicas remained. Grid spacing adapted to the larger extent
and was reported to the user. Camera/material-only changes caused no rebuild.
Source coordinates were unchanged, with no browser page errors.

At 960 × 640, completed rendering **plus full pixel readback** took median
1.84 s with the surface and 4.37 s with molecular spheres over three samples
(first sample included warm-up). This test used **Chromium's SwiftShader software
renderer**, not the Mac's native GPU: the roughly 2.4× comparison demonstrates
reduced rendering work, not native FPS or a universal performance guarantee.
CPU draw-submission timing alone is not used as frame-rate evidence.

The supplied file contains one snapshot. Moving-water coverage therefore uses
the synthetic 24-frame example and changing-topology browser regressions, not a
claim that this user's full MD trajectory was tested. The application-exported
960 × 640 GIF was regenerated and its first/middle frames inspected. Exact-size
PNG, offline HTML, project round-trip, selection, undo/redo and error recovery are
also covered. Large real trajectories remain a prerequisite for main integration.

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
