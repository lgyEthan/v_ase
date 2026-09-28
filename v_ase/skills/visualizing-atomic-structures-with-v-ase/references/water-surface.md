# Water surface

## Contents

- [Source scope and exports](#source-scope-and-exports)
- [Shared renderer quality](#shared-renderer-quality)

## Source scope and exports

Discover `capabilities().waterSurface` and `display.waterSurface` in the live display schema. Read `describe().analysis.waterSurface` for build/error diagnostics. Use the existing typed
display control, preserving document/revision preconditions. Read and merge the
current nested water settings when modifying one field; the object carries its
own defaults. The following camelCase payload is for HTTP `apply` parameters
(or the browser API), not a native tool's snake_case arguments. Example display payload:

```json
{"waterSurface":{"enabled":true,"source":"auto","color":"#65aaca","opacity":0.48,"lighting":true,"hideMolecules":true,"smoothing":2.0,"level":0.63,"spacing":0.65,"ohCutoff":1.25,"roughness":0.18,"indices":[]}}
```

For native/MCP calls, first read `vase_tool_schema` for `vase_set_display`, then
call **`vase_set_display`** with the following snake_case payload. Replace the
example document ID and revision with the latest summary. Do not put these
renderer fields in `vase_apply_scene.patch.display`: that semantic subset does
not accept arbitrary display controls.

```json
{"display":{"water_surface":{"enabled":true,"source":"auto","smoothing":2.0,"level":0.63,"spacing":0.65,"color":"#65aaca","opacity":0.48,"lighting":true,"hide_molecules":true,"oh_cutoff":1.25,"roughness":0.18,"indices":[]},"water_interpolation":1,"water_mesh_smoothing":20},"expected_document_id":"FROM_LATEST_SUMMARY","expected_revision":0}
```

`source:"selected"` uses captured **oxygen base indices**, not the current GUI
selection. Empty indices select no molecules; indices missing in a short frame
are retained. Detection uses actual elements and valid positive source molecule IDs first
(`mol`, `molecule_id`, `molecule_ids`, `molid`, `mol-id`), with nearest O–H fallback only for
unassigned atoms. A declared molecule must contain one O and two H and satisfy
the periodic O–H cutoff. Mutable labels and visual bond settings do not define
water. Read `method`, `topologyMolecules`, `builds`, `vertices`, `triangles`,
`spacing` and `buildMs` in the water report.

This is a Gaussian-density isosurface for presentation, not fluid/MD simulation
or a physical mass-density measurement. Smoothing can bridge small gaps. Never
claim a membrane permeability, liquid boundary or new scientific result from it.
Source coordinates, chemical elements and constraints must remain unchanged.

The GUI is **Style → Water**; Objects shares its enabled checkbox. `lighting:false`
uses an unlit surface while preserving other objects' lighting. Surface material
is unlit in flat mode. The same geometry path serves viewport, PNG/movie/GIF and
self-contained HTML; project settings persist in .vase. Blender export includes the editable water mesh, material, periodic copies and
per-frame geometry. A NumPy/SciPy surface-nets implementation is tested against the
viewport mesh including fairing/subdivision. Export errors above four million
refined water triangles/frame or two million total animation sites/vertices must
be resolved by reducing subdivision/repetitions/frame count, not by silently
omitting water. Run the generated script in Blender; run it again after reopening
for procedural trajectory playback. OBJ/3DM still reject enabled water.

Capacity failures appear in the water status and restore molecular spheres.
Interior sphere/bond instances are excluded from GPU draw counts. An indexed
boundary mesh is cached during camera/material changes, rebuilt for coordinates
and displayed signed supercell offsets, and shared by exact exports.
The prototype bounds grid size/kernel work and displayed molecule counts;
do not claim arbitrary-size realtime performance. Use the synthetic
`examples/water_surface.py` only as rendering evidence, not physical simulation.

Stored molecule IDs stay synchronized with streamed coordinates, even while the
layer is off. If water-enabled video interpolation reports changed molecule IDs,
export source frames with `interpolationMultiplier:1`; never interpolate molecule
identity. In-memory fixed-topology trajectories keep their coordinate cache; lazy
sources that may change IDs use one synchronized frame response. Capacity errors
restore atom glyphs, and returning to valid settings rebuilds the envelope.

## Shared renderer quality

Discover `capabilities().rendererQuality`. In the existing typed `display` patch,
set `atomSmoothness` to an even integer 8–128 to control atom and cylindrical bond
tessellation together. `0` preserves old quality presets. Numeric quality applies
to the viewport and default image/movie output; explicit legacy export overrides
remain available. Scientific bond lengths and radii do not change. Projected-size
LOD targets 0.2 drawing-buffer-pixel silhouette error up to that ceiling, and
culls off-screen instances while retaining shadow casters. The interactive
20-million-triangle preflight can select 12 segments; reread display state after
an extreme request rather than claiming the requested setting was accepted.

`waterInterpolation` and `isosurfaceInterpolation` are integers 0–8; each level
multiplies base triangles by four. `waterMeshSmoothing` and
`isosurfaceMeshSmoothing` are independent integers 0–100. They perform Taubin
fairing on a display copy of the base mesh before subdivision, pinning open and
nonmanifold boundary vertices. Source fields, isovalues and atom coordinates do
not change; displayed interior vertices can move. Try 20 smoothing passes with
subdivision 1 to soften ripples without excessive triangle growth. Subdivision
alone preserves original vertices and cannot remove their noise. Do not claim
smoothing preserves exact volume or adds scientific data.

More than 8,000,000 output triangles per surface or 12,000,000 combined is rejected
before expansion; reduce subdivision before retrying. Image/movie capture waits
for current finished geometry; fast live trajectories keep the last completed
surface while refinement runs. Renderer controls are disabled without a visible
matching surface; enable an actual isosurface in Style → Isosurfaces first.
Isovalue and field generation belong there, not in Renderer → Quality. A section
plane alone is insufficient. `capabilities().rendererQuality` reports the
subdivisionRange, smoothing fields/range, isovalueRoute and availability rule.

GUI controls live under Renderer → Quality. Cancel/Esc stops cooperative work,
Revert quality restores the preceding setting, Lightweight resets segments to 12
and both subdivision and smoothing settings to zero. These display fields persist in .vase and
self-contained HTML. Use this recovery in capacity tests; never claim arbitrary
real-time performance. Test scientific coordinates and instance identities before
and after a quality change, and inspect a magnified render, not only HTTP success.

New scenes use a 2.0 Å kernel / 0.63 threshold (~1.92 Å isolated footprint),
water subdivision 1 and 20 mesh smoothing passes. Saved explicit values,
including zero finish, must survive loading. These are visual defaults derived
from a molecular length scale, not a calibrated liquid density boundary.
